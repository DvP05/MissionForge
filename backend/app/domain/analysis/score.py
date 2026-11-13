"""Weighted game score (architecture 7.11). Pure; independent of hard feasibility.

The score is shown for learning even when a hard gate fails, but it can never make a
failed design mission-ready (see ``constraints.mission_ready``). Component price or mass
reduction is never rewarded in isolation: resource stewardship depends only on whether the
total cost stays within budget.
"""

from collections.abc import Sequence

from app.domain.analysis.constraints import (
    data_return_margin_fraction,
    energy_margin_fraction,
    reserve_ms,
)
from app.domain.analysis.context import AnalysisContext
from app.schemas.analysis import ConstraintResult, ScoreBreakdown, ScoreDimension, ScoreDimensionId

WEIGHTS: tuple[tuple[ScoreDimensionId, float], ...] = (
    ("scientific-return", 30.0),
    ("mission-execution", 25.0),
    ("engineering-robustness", 20.0),
    ("resource-stewardship", 15.0),
    ("operations-quality", 10.0),
)

# Hard-gate ids counted by the mission-execution proxy ("compat-*" matched by prefix).
HARD_GATE_IDS = frozenset(
    {
        "mass-launch-limit",
        "delta-v-margin",
        "peak-power",
        "energy-closure",
        "data-buffer",
        "link-margin",
        "battery-reserve",
        "trajectory-valid",
        "science-mandatory-coverage",
        "budget",
    }
)
_GATE_CREDIT = {"pass": 1.0, "warning": 0.5, "fail": 0.0}
_OVERFLOW_FACTOR = 0.5

SCORE_ASSUMPTIONS: tuple[str, ...] = (
    "Weights 30/25/20/15/10 are displayed and sum to 100; total = sum(weight x score / 100).",
    "scientific-return = ScienceAnalysis.coverage_score (returned data, not merely collected).",
    "mission-execution is a design-time proxy; refined by simulation: 100 x mean credit over "
    "hard gates (pass 1, warning 0.5, fail 0); not-modelled gates are excluded.",
    "engineering-robustness = mean of clamp(headroom / required headroom, 0, 1) x 100 over the "
    "mass, delta-v, energy and data margins that can be evaluated.",
    "resource-stewardship = 100 within budget, falling linearly to 0 at twice the budget; "
    "a cheaper design inside the budget scores the same, so cost alone is never rewarded.",
    "operations-quality is a design-time proxy; refined by simulation: 100 x share of planned "
    "contacts with non-negative link margin x (0.5 if the buffer overflows).",
)


def _clamp01(x: float) -> float:
    return min(1.0, max(0.0, x))


def _credit(headroom: float, required: float) -> float:
    """clamp(headroom / required_headroom, 0, 1): 1 exactly at the hard-gate threshold,
    0 at zero raw headroom."""
    if required <= 0.0:
        return 1.0 if headroom >= 0.0 else 0.0
    return _clamp01(headroom / required)


def _is_gate(c: ConstraintResult) -> bool:
    return c.id in HARD_GATE_IDS or c.id.startswith("compat-")


def _execution(constraints: Sequence[ConstraintResult]) -> tuple[float, str]:
    credits = [
        _GATE_CREDIT[c.status] for c in constraints if _is_gate(c) and c.status in _GATE_CREDIT
    ]
    if not credits:
        return 0.0, "No hard gate could be evaluated (design-time proxy; refined by simulation)."
    score = 100.0 * sum(credits) / len(credits)
    return score, (
        f"{sum(1 for x in credits if x == 1.0)} of {len(credits)} hard gates pass "
        "(design-time proxy; refined by simulation)."
    )


def _robustness(ctx: AnalysisContext) -> tuple[float, str]:
    lim = ctx.limits
    credits: list[float] = []
    if lim.launch_mass_limit_kg is not None:
        limit = lim.launch_mass_limit_kg
        required = 1.0 - 1.0 / (1.0 + lim.mass_margin_fraction)
        credits.append(_credit((limit - ctx.mass.wet_kg) / limit, required))
    b = ctx.maneuvers
    credits.append(_credit(b.available_ms - b.required_ms, reserve_ms(b)))
    energy = energy_margin_fraction(ctx)
    if energy is not None:
        credits.append(_credit(energy, lim.power_margin_fraction))
    data = data_return_margin_fraction(ctx)
    if data is not None:
        credits.append(_credit(data, lim.data_margin_fraction))
    score = 100.0 * sum(credits) / len(credits)
    return score, (
        f"Mean of {len(credits)} mass, delta-v, energy and data headrooms relative to the "
        "required headroom (full credit at the hard-gate threshold, zero at no headroom)."
    )


def _stewardship(ctx: AnalysisContext) -> tuple[float, str]:
    total, budget = ctx.cost.total, ctx.limits.maximum_budget_usd
    if total <= budget:
        return 100.0, (
            f"Cost ${total:,.0f} is within the ${budget:,.0f} budget; spending less is not "
            "rewarded on its own."
        )
    score = 100.0 * _clamp01(1.0 - (total - budget) / budget)
    return score, f"Cost ${total:,.0f} exceeds the ${budget:,.0f} budget, which lowers the score."


def _operations(ctx: AnalysisContext) -> tuple[float, str]:
    links = ctx.contact_links
    if not links:
        return 0.0, ("No downlink contacts are planned (design-time proxy; refined by simulation).")
    closing = sum(1 for lk in links if lk.margin_db >= 0.0)
    factor = 1.0 if ctx.data.overflow_bits <= 0.0 else _OVERFLOW_FACTOR
    score = 100.0 * closing / len(links) * factor
    overflow = "" if factor == 1.0 else " and the data buffer overflows (halved)"
    return score, (
        f"{closing} of {len(links)} planned contacts close{overflow} "
        "(design-time proxy; refined by simulation)."
    )


def score_preview(ctx: AnalysisContext, constraints: Sequence[ConstraintResult]) -> ScoreBreakdown:
    science = ctx.science.coverage_score
    parts: dict[ScoreDimensionId, tuple[float, str]] = {
        "scientific-return": (
            science,
            f"Returned-data science coverage is {science:.0f} of 100 (collected data that is "
            "not downlinked does not count).",
        ),
        "mission-execution": _execution(constraints),
        "engineering-robustness": _robustness(ctx),
        "resource-stewardship": _stewardship(ctx),
        "operations-quality": _operations(ctx),
    }
    dims: list[ScoreDimension] = []
    total = 0.0
    for dim_id, weight in WEIGHTS:
        value, why = parts[dim_id]
        value = min(100.0, max(0.0, value))
        dims.append(ScoreDimension(id=dim_id, weight=weight, score=value, explanation=why))
        total += weight * value / 100.0
    return ScoreBreakdown(total=total, dimensions=tuple(dims))

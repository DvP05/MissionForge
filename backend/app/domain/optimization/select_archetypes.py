"""Lean / Science-max / Resilient representatives by transparent rules (19.2 step 5)."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from app.schemas.analysis import MissionAnalysis
from app.schemas.optimization import Archetype

# Resilient must still do real science: at least this share of the best feasible score.
RESILIENT_MIN_SCIENCE_SHARE = 0.5
RESILIENT_POOL = 10


@dataclass(frozen=True)
class Scored:
    id: str
    analysis: MissionAnalysis


def margin_proxy(a: MissionAnalysis) -> float:
    """Worst normalised margin: a fast stand-in for robustness (bigger is sturdier).

    Undefined margins (R38 None) are skipped rather than read as 0; a design with no
    defined margin at all ranks last (``-inf``). The value is only used for ordering.
    """
    b = a.budgets
    required_dv = float(b.required_delta_v_km_per_s.value)
    dvm = b.delta_v_margin_km_per_s
    dv = None if dvm is None else (dvm / required_dv if required_dv > 0 else 1.0)
    defined = [
        m
        for m in (b.mass_margin_fraction, b.energy_margin_fraction, b.data_margin_fraction, dv)
        if m is not None
    ]
    return min(defined) if defined else float("-inf")


def _cost(a: MissionAnalysis) -> float:
    return float(a.budgets.estimated_cost_usd.value)


def _science(a: MissionAnalysis) -> float:
    return a.science.coverage_score


def resilient_pool(feasible: Sequence[Scored], front: Sequence[str]) -> list[Scored]:
    """Front members plus the best margin-proxy designs, science floor applied, capped."""
    if not feasible:
        return []
    best_science = max(_science(c.analysis) for c in feasible)
    floor = RESILIENT_MIN_SCIENCE_SHARE * best_science
    eligible = [c for c in feasible if _science(c.analysis) >= floor]
    by_proxy = sorted(eligible, key=lambda c: (-margin_proxy(c.analysis), c.id))
    front_set = set(front)
    ordered = [c for c in eligible if c.id in front_set] + by_proxy
    pool: dict[str, Scored] = {}
    for c in ordered:
        if len(pool) >= RESILIENT_POOL:
            break
        pool.setdefault(c.id, c)
    return list(pool.values())


def select_archetypes(
    feasible: Sequence[Scored],
    front: Sequence[str],
    *,
    robustness: Mapping[str, float] | None = None,
    robustness_samples: int = 0,
) -> tuple[dict[Archetype, str], dict[str, list[str]]]:
    """Return archetype -> candidate id, plus explanation lines per chosen candidate.

    `robustness` maps candidate id -> probability of staying feasible for the designs that
    were checked; without it Resilient falls back to the margin proxy (and says so).
    """
    if not feasible:
        return {}, {}
    n = len(feasible)
    notes: dict[str, list[str]] = {}

    def pick(key: Callable[[Scored], tuple[float, float, str]]) -> Scored:
        return min(feasible, key=key)

    lean = pick(lambda c: (_cost(c.analysis), -_science(c.analysis), c.id))
    sci = pick(lambda c: (-_science(c.analysis), _cost(c.analysis), c.id))
    notes.setdefault(lean.id, []).append(
        f"Lean: lowest estimated cost ({_cost(lean.analysis):,.0f} USD) among {n} feasible designs."
    )
    notes.setdefault(sci.id, []).append(
        f"Science-max: highest science coverage score ({_science(sci.analysis):.1f}) among "
        f"{n} feasible designs."
    )

    pool = resilient_pool(feasible, front)
    checked = {c.id: robustness[c.id] for c in pool if robustness and c.id in robustness}
    if checked:
        res = min(
            pool,
            key=lambda c: (-checked.get(c.id, -1.0), -margin_proxy(c.analysis), c.id),
        )
        notes.setdefault(res.id, []).append(
            f"Resilient: stayed feasible in {checked[res.id]:.0%} of {robustness_samples} "
            f"robustness samples, the best of {len(checked)} checked designs that keep at least "
            f"{RESILIENT_MIN_SCIENCE_SHARE:.0%} of the best science score."
        )
    else:
        res = min(pool, key=lambda c: (-margin_proxy(c.analysis), c.id))
        notes.setdefault(res.id, []).append(
            "Resilient (proxy): largest worst-case margin among designs that keep at least "
            f"{RESILIENT_MIN_SCIENCE_SHARE:.0%} of the best science score; robustness samples "
            "were not run."
        )
    return {"lean": lean.id, "science-max": sci.id, "resilient": res.id}, notes

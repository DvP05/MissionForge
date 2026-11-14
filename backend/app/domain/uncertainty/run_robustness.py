"""Seeded Monte Carlo robustness run over the deterministic engine (architecture 19.3)."""

from collections.abc import Callable, Sequence
from datetime import datetime

from app.domain.analysis.orchestrator import ScenarioInputs, analyze_mission
from app.domain.catalog.loader import Catalog
from app.domain.errors import DomainValidationError
from app.domain.uncertainty.paths import apply_samples, require_allowed
from app.domain.uncertainty.samplers import rng_for, sample
from app.domain.uncertainty.wilson_interval import wilson_interval
from app.schemas.analysis import MissionAnalysis
from app.schemas.mission import MissionState
from app.schemas.uncertainty import MetricQuantiles, RobustnessResult, UncertaintyProfile

MAX_SAMPLES = 1000

DISCLAIMER = (
    "Game-level robustness proxy: seeded Monte Carlo over simplified subsystem models. "
    "It is not a flight-qualified probabilistic risk assessment, a covariance propagator "
    "or chance-constrained optimal control."
)


class RobustnessLimitExceeded(DomainValidationError):  # noqa: N818
    def __init__(self, requested: int) -> None:
        super().__init__(
            "SIMULATION_LIMIT_EXCEEDED",
            "samples",
            f"{requested} samples requested; the limit is {MAX_SAMPLES}",
        )


_METRICS: tuple[tuple[str, str, Callable[[MissionAnalysis], float]], ...] = (
    ("wetMassKg", "kg", lambda a: float(a.budgets.wet_mass_kg.value)),
    ("deltaVMarginKmPerS", "km/s", lambda a: a.budgets.delta_v_margin_km_per_s),
    ("energyMarginFraction", "fraction", lambda a: a.budgets.energy_margin_fraction),
    ("dataMarginFraction", "fraction", lambda a: a.budgets.data_margin_fraction),
    ("returnedFraction", "fraction", lambda a: a.science.returned_fraction),
    ("scienceCoverageScore", "points", lambda a: a.science.coverage_score),
    ("scoreTotal", "points", lambda a: a.score.total),
)


def quantile(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolation quantile (same as numpy 'linear') of a non-empty sorted list."""
    if not sorted_values:
        raise DomainValidationError("INVALID_SAMPLE_COUNT", "values", "no values")
    pos = (len(sorted_values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def run_robustness(
    state: MissionState,
    profile: UncertaintyProfile,
    catalog: Catalog,
    *,
    scenario: ScenarioInputs,
    n: int,
    seed: int,
    engine_version: str,
    now: datetime,
) -> RobustnessResult:
    """Re-run the engine on `n` perturbed clones of the design. Inputs are never mutated."""
    if n < 1:
        raise DomainValidationError("INVALID_SAMPLE_COUNT", "samples", "need at least 1 sample")
    if n > MAX_SAMPLES:
        raise RobustnessLimitExceeded(n)
    for p in profile.parameters:
        require_allowed(p.path)

    feasible = 0
    clamped = 0
    failures: dict[str, int] = {}
    series: dict[str, list[float]] = {name: [] for name, _, _ in _METRICS}
    for i in range(n):
        values: dict[str, float] = {}
        for p in profile.parameters:
            draw = sample(p.distribution, rng_for(seed, i, p.id))
            if p.path in values:  # two parameters on one path compose
                spec_scale = require_allowed(p.path).mode == "scale"
                draw = values[p.path] * draw if spec_scale else values[p.path] + draw
            values[p.path] = draw
        applied = apply_samples(state, catalog, values)
        clamped += applied.clamped
        analysis = analyze_mission(
            applied.state,
            applied.catalog,
            scenario=scenario,
            engine_version=engine_version,
            now=now,
        )
        if analysis.feasibility != "infeasible":
            feasible += 1
        for c in analysis.constraints:
            if c.status == "fail":
                failures[c.id] = failures.get(c.id, 0) + 1
        for name, _, read in _METRICS:
            series[name].append(read(analysis))

    metrics = {}
    for name, unit, _ in _METRICS:
        ordered = sorted(series[name])
        metrics[name] = MetricQuantiles(
            p10=quantile(ordered, 0.1),
            median=quantile(ordered, 0.5),
            p90=quantile(ordered, 0.9),
            unit=unit,
        )

    assumptions = [
        f"{p.id} ({p.kind}, {p.distribution.kind}): {p.rationale}" for p in profile.parameters
    ]
    assumptions += [
        "Each sample perturbs a copy of the design and the selected catalogue parts, then "
        "re-runs the same deterministic engine; nothing else is modelled.",
        "Parameters are sampled independently of each other; one mass-growth factor applies "
        "to every selected component in a sample (fully correlated).",
        "Epistemic ranges are sampled as a sensitivity sweep; the result is not a true "
        "probability for those parameters.",
        "'Feasible' means no hard constraint failed (warnings still count as feasible).",
    ]
    if clamped:
        assumptions.append(
            f"{clamped} sampled fraction values fell outside [0, 1] and were clamped to the "
            "physical bound."
        )
    return RobustnessResult(
        samples=n,
        seed=seed,
        probability_feasible=feasible / n,
        feasibility_wilson_95=wilson_interval(feasible, n),
        metrics=metrics,
        failure_counts=dict(sorted(failures.items(), key=lambda kv: (-kv[1], kv[0]))),
        profile_version=f"{profile.id}@{profile.version}",
        assumptions=assumptions,
        disclaimer=DISCLAIMER,
    )

"""Educational Monte Carlo robustness evaluation."""

import math
import random
from collections.abc import Callable, Mapping, Sequence

from app.schemas.analysis import MissionAnalysis
from app.schemas.mission import MissionState
from app.schemas.uncertainty import (
    DistributionSpec,
    MetricQuantiles,
    RobustnessResult,
    UncertaintyProfile,
)


def sample_distribution(spec: DistributionSpec, rng: random.Random) -> float:
    """Sample one validated distribution using the supplied deterministic RNG."""
    if spec.kind == "normal":
        assert spec.mean is not None and spec.std_dev is not None
        value = rng.gauss(spec.mean, spec.std_dev)
        if spec.min is not None:
            value = max(spec.min, value)
        if spec.max is not None:
            value = min(spec.max, value)
        return value
    if spec.kind == "uniform":
        assert spec.min is not None and spec.max is not None
        return rng.uniform(spec.min, spec.max)
    assert spec.min is not None and spec.max is not None and spec.mode is not None
    return rng.triangular(spec.min, spec.max, spec.mode)


def sample_profile(
    profile: UncertaintyProfile, samples: int, seed: int
) -> dict[str, tuple[float, ...]]:
    if samples < 0:
        raise ValueError("samples must be >= 0")
    rng = random.Random(seed)
    return {
        parameter.id: tuple(
            sample_distribution(parameter.distribution, rng) for _ in range(samples)
        )
        for parameter in profile.parameters
    }


def _quantile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def wilson_interval(successes: int, samples: int) -> tuple[float, float]:
    if samples == 0:
        return 0.0, 0.0
    z = 1.959963984540054
    p = successes / samples
    denominator = 1 + z * z / samples
    centre = (p + z * z / (2 * samples)) / denominator
    spread = z * math.sqrt((p * (1 - p) + z * z / (4 * samples)) / samples) / denominator
    return max(0.0, centre - spread), min(1.0, centre + spread)


def _analysis_metrics(analysis: MissionAnalysis) -> dict[str, tuple[float, str]]:
    return {
        "dry_mass_kg": (analysis.budgets.dry_mass_kg.value, "kg"),
        "energy_margin_fraction": (analysis.budgets.energy_margin_fraction, "fraction"),
        "data_margin_fraction": (analysis.budgets.data_margin_fraction, "fraction"),
        "science_coverage_score": (analysis.science.coverage_score, "%"),
    }


SampleEvaluator = Callable[[MissionState, Mapping[str, float]], MissionAnalysis]


def run_robustness(
    state: MissionState,
    profile: UncertaintyProfile,
    evaluate: SampleEvaluator,
    *,
    samples: int,
    seed: int,
) -> RobustnessResult:
    """Evaluate each seeded sample and return explainable empirical statistics."""
    sampled = sample_profile(profile, samples, seed)
    analyses: list[MissionAnalysis] = []
    for index in range(samples):
        values = {parameter_id: values[index] for parameter_id, values in sampled.items()}
        analyses.append(evaluate(state, values))

    successes = sum(analysis.feasibility != "infeasible" for analysis in analyses)
    failures: dict[str, int] = {}
    for analysis in analyses:
        for constraint in analysis.constraints:
            if constraint.status == "fail":
                failures[constraint.id] = failures.get(constraint.id, 0) + 1

    metric_values: dict[str, list[float]] = {}
    metric_units: dict[str, str] = {}
    for analysis in analyses:
        for key, (value, unit) in _analysis_metrics(analysis).items():
            metric_values.setdefault(key, []).append(value)
            metric_units[key] = unit
    metrics = {
        key: MetricQuantiles(
            p10=_quantile(values, 0.1),
            median=_quantile(values, 0.5),
            p90=_quantile(values, 0.9),
            unit=metric_units[key],
        )
        for key, values in metric_values.items()
    }
    return RobustnessResult(
        samples=samples,
        seed=seed,
        probability_feasible=successes / samples if samples else 0.0,
        feasibility_wilson_95=wilson_interval(successes, samples),
        metrics=metrics,
        failure_counts=failures,
        profile_version=profile.version,
        assumptions=[
            "Samples are independent unless a profile explicitly supplies a shared parameter.",
            "This is an educational robustness proxy, not flight-qualified reliability.",
        ],
        disclaimer=(
            "Feasibility fraction is an empirical gameplay estimate, not mission reliability."
        ),
    )

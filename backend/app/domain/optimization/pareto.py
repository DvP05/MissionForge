"""Bounded candidate generation and Pareto selection."""

import random
from collections.abc import Callable, Mapping, Sequence

from app.domain.catalog.loader import Catalog
from app.schemas.analysis import MissionAnalysis
from app.schemas.mission import MissionState
from app.schemas.optimization import (
    Archetype,
    ArchitectureCandidate,
    OptimizationObjective,
    OptimizationResult,
)

Evaluator = Callable[[MissionState], MissionAnalysis]

DEFAULT_OBJECTIVES: tuple[OptimizationObjective, ...] = (
    OptimizationObjective(key="lifecycle_cost", direction="minimize", weight=1.0),
    OptimizationObjective(key="dry_mass", direction="minimize", weight=1.0),
    OptimizationObjective(key="negative_science_return", direction="minimize", weight=1.0),
)


def _value(analysis: MissionAnalysis, key: str) -> float:
    values = {
        "lifecycle_cost": analysis.budgets.estimated_cost_usd.value,
        "dry_mass": analysis.budgets.dry_mass_kg.value,
        "duration_days": 0.0,
        "negative_science_return": -analysis.science.returned_fraction,
        "negative_robustness": -analysis.reliability.nominal_reliability,
    }
    return values[key]


def _normalise(values: Sequence[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.0 for _ in values]
    return [(value - lo) / (hi - lo) for value in values]


def dominates(a: Mapping[str, float], b: Mapping[str, float]) -> bool:
    """Return whether minimisation vector ``a`` dominates ``b``."""
    shared = set(a) & set(b)
    return bool(shared) and all(a[key] <= b[key] for key in shared) and any(
        a[key] < b[key] for key in shared
    )


def pareto_front(candidates: Sequence[ArchitectureCandidate]) -> list[str]:
    feasible = [candidate for candidate in candidates if candidate.feasible]
    return [
        candidate.id
        for candidate in feasible
        if not any(
            other.id != candidate.id
            and dominates(other.objective_vector, candidate.objective_vector)
            for other in feasible
        )
    ]


def _mutations(state: MissionState, catalog: Mapping[str, object], seed: int) -> list[MissionState]:
    rng = random.Random(seed)
    fields = (
        "launch_vehicle_id", "bus_id", "propulsion_id", "power_id", "adcs_id",
        "communications_id", "thermal_id", "cdh_id", "ground_segment_id",
    )
    options: list[tuple[str, str]] = []
    for field in fields:
        category = field.removesuffix("_id")
        options.extend(
            (field, component_id)
            for component_id, component in catalog.items()
            if getattr(component, "category", None) == category
        )
    options.sort()
    rng.shuffle(options)
    mutations: list[MissionState] = [state]
    for field, component_id in options:
        architecture = state.architecture.model_copy(update={field: component_id})
        mutations.append(state.model_copy(update={"architecture": architecture}))
    return mutations


def optimize_mission(
    state: MissionState,
    catalog: Mapping[str, object] | Catalog,
    evaluate: Evaluator,
    *,
    seed: int | None = None,
    objectives: Sequence[OptimizationObjective] = DEFAULT_OBJECTIVES,
    max_candidates: int = 50,
) -> OptimizationResult:
    """Evaluate a deterministic bounded mutation set using the canonical evaluator."""
    actual_seed = state.random_seed if seed is None else seed
    states = _mutations(state, catalog, actual_seed)[: max(1, max_candidates)]
    analyses = [evaluate(candidate) for candidate in states]
    raw = [[_value(analysis, objective.key) for objective in objectives] for analysis in analyses]
    columns = list(zip(*raw, strict=True))
    normalized_columns = [_normalise(column) for column in columns]
    candidates: list[ArchitectureCandidate] = []
    for index, (candidate_state, analysis) in enumerate(zip(states, analyses, strict=True)):
        vector = {
            objective.key: normalized_columns[objective_index][index]
            for objective_index, objective in enumerate(objectives)
        }
        feasible = analysis.feasibility != "infeasible"
        candidates.append(
            ArchitectureCandidate(
                id=f"candidate-{index:03d}",
                mission_state=candidate_state,
                analysis=analysis,
                objective_vector=vector,
                feasible=feasible,
                generation=0,
                explanation=[
                    "Feasible candidate evaluated by the canonical mission analysis engine."
                    if feasible
                    else (
                        "Near miss retained for diagnosis because at least one hard "
                        "constraint failed."
                    )
                ],
            )
        )
    front = pareto_front(candidates)
    feasible_candidates = [candidate for candidate in candidates if candidate.id in front]
    if not feasible_candidates:
        archetypes: dict[Archetype, str] = {}
    else:
        def best(key: str, reverse: bool = False) -> str:
            return sorted(
                feasible_candidates,
                key=lambda candidate: (candidate.objective_vector[key], candidate.id),
                reverse=reverse,
            )[0].id

        archetypes = {
            "lean": best("dry_mass"),
            "science-max": best("negative_science_return"),
            "resilient": best("negative_robustness"),
        }
    return OptimizationResult(
        seed=actual_seed,
        objectives=list(objectives),
        candidates=candidates,
        pareto_front_ids=front,
        archetypes=archetypes,
        near_misses=[candidate.id for candidate in candidates if not candidate.feasible],
    )

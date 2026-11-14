"""Run the Mission Design Arena: generate, analyse, filter, front, archetypes (19.2)."""

from datetime import datetime

from app.domain.analysis.orchestrator import ScenarioInputs, analyze_mission
from app.domain.catalog.loader import Catalog
from app.domain.optimization.dominates import pareto_front
from app.domain.optimization.generate_candidates import (
    Change,
    generate_candidates,
)
from app.domain.optimization.select_archetypes import (
    Scored,
    resilient_pool,
    select_archetypes,
)
from app.domain.uncertainty.run_robustness import run_robustness
from app.schemas.analysis import MissionAnalysis
from app.schemas.mission import MissionState
from app.schemas.optimization import (
    ArchitectureCandidate,
    ObjectiveKey,
    OptimizationObjective,
    OptimizationResult,
)
from app.schemas.uncertainty import UncertaintyProfile

MAX_RESILIENCE_SAMPLES = 50
MAX_ANCHORS = 3

# Dominance objectives, all minimised (science is negated). Weights stay None: ranking
# preferences are never used for dominance.
OBJECTIVES: tuple[OptimizationObjective, ...] = (
    OptimizationObjective(key="lifecycle_cost", direction="minimize"),
    OptimizationObjective(key="dry_mass", direction="minimize"),
    OptimizationObjective(key="negative_science_return", direction="minimize"),
)


def _fail_count(a: MissionAnalysis) -> int:
    return sum(c.status == "fail" for c in a.constraints)


def objective_vector(a: MissionAnalysis) -> dict[ObjectiveKey, float]:
    return {
        "lifecycle_cost": float(a.budgets.estimated_cost_usd.value),
        "dry_mass": float(a.budgets.dry_mass_kg.value),
        "negative_science_return": -a.science.coverage_score,
    }


def optimize(
    base: MissionState,
    catalog: Catalog,
    *,
    scenario: ScenarioInputs,
    seed: int,
    cap: int,
    engine_version: str,
    now: datetime,
    profile: UncertaintyProfile | None = None,
    robustness_samples: int = 0,
) -> OptimizationResult:
    """Deterministic for the same base, catalogue, seed, cap and sample count."""
    samples = max(0, min(robustness_samples, MAX_RESILIENCE_SAMPLES))
    analyses: dict[str, MissionAnalysis] = {}

    def analyse(design_id: str, state: MissionState) -> MissionAnalysis:
        if design_id not in analyses:
            analyses[design_id] = analyze_mission(
                state, catalog, scenario=scenario, engine_version=engine_version, now=now
            )
        return analyses[design_id]

    # Pass 1: which single changes leave fewer hard failures than the baseline?
    first = generate_candidates(base, catalog, seed=seed, cap=cap)
    base_fails = _fail_count(analyse(first[0].id, first[0].state))
    singles = {(d.changes[0]): d for d in first if d.generation == 1}
    ranked = sorted(
        (c for c, d in singles.items() if _fail_count(analyse(d.id, d.state)) < base_fails),
        key=lambda c: (_fail_count(analyses[singles[c].id]), c.describe()),
    )
    anchors: list[Change] = ranked[:MAX_ANCHORS]
    # Pass 2: explore around those improvements first (same seed, so still deterministic).
    designs = generate_candidates(base, catalog, seed=seed, cap=cap, anchors=anchors)
    for d in designs:
        analyse(d.id, d.state)
    feasible = [
        Scored(d.id, analyses[d.id]) for d in designs if analyses[d.id].feasibility != "infeasible"
    ]
    keys = [o.key for o in OBJECTIVES]
    vectors = {c.id: [objective_vector(c.analysis)[k] for k in keys] for c in feasible}
    front = pareto_front(vectors)

    robustness: dict[str, float] = {}
    if samples and profile is not None:
        by_id = {d.id: d for d in designs}
        for c in resilient_pool(feasible, front):
            result = run_robustness(
                by_id[c.id].state,
                profile,
                catalog,
                scenario=scenario,
                n=samples,
                seed=seed,
                engine_version=engine_version,
                now=now,
            )
            robustness[c.id] = result.probability_feasible
    archetypes, notes = select_archetypes(
        feasible, front, robustness=robustness or None, robustness_samples=samples
    )

    front_set = set(front)
    candidates = []
    for d in designs:
        a = analyses[d.id]
        explanation = [ch.describe() for ch in d.changes] or [
            "Baseline design (your current revision)."
        ]
        if a.feasibility == "infeasible":
            failed = [c.label for c in a.constraints if c.status == "fail"]
            explanation.append("Near miss: fails " + ", ".join(failed) + ".")
        elif d.id in front_set:
            explanation.append(
                "On the Pareto front: no other feasible design is at least as cheap, as light "
                "and as scientific while being better on one of them."
            )
        if d.id in robustness:
            explanation.append(
                f"Stayed feasible in {robustness[d.id]:.0%} of {samples} robustness samples."
            )
        explanation += notes.get(d.id, [])
        candidates.append(
            ArchitectureCandidate(
                id=d.id,
                mission_state=d.state,
                analysis=a,
                objective_vector=dict(objective_vector(a)),
                feasible=a.feasibility != "infeasible",
                generation=d.generation,
                explanation=explanation,
            )
        )
    return OptimizationResult(
        seed=seed,
        objectives=list(OBJECTIVES),
        candidates=candidates,
        pareto_front_ids=front,
        archetypes=archetypes,
        near_misses=[d.id for d in designs if analyses[d.id].feasibility == "infeasible"],
    )

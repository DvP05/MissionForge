"""Evidence Passport v2 (Task 6.9): Phase 6 evidence recomputed from a run's snapshot.

Everything is recomputed server-side from ``run.input_snapshot`` with seeds taken from the
mission's ``random_seed``, so the passport never relies on client-supplied research
results and the same run always yields the same research evidence. No HTTP types here.
"""

from datetime import datetime

from app.domain.optimization import dominates
from app.schemas.evidence import ParetoPosition, ResearchEvidence
from app.schemas.health import HealthFinding
from app.schemas.mission import MissionState
from app.schemas.optimization import (
    MissionTraceRowOut,
    OptimizationResult,
    ScienceTraceRowOut,
)
from app.schemas.simulation import MissionRun
from app.services.graph_service import GraphService
from app.services.health_monitor_service import HealthMonitorService
from app.services.optimization_service import OptimizationService
from app.services.robustness_service import RobustnessService
from app.services.schedule_service import ScheduleService

# Kept small so an export stays around a second or two (250 candidates < 3 s, 250
# samples < 2 s in the Phase 6 budgets).
PASSPORT_PARETO_CANDIDATES = 100
PASSPORT_ROBUSTNESS_SAMPLES = 100
MAX_DOMINATED_BY = 5

BELIEF_NOTE = (
    "The science belief tracker is interactive (player-chosen observations) and is not "
    "recorded in a run, so no posterior is included here."
)


def pareto_position(result: OptimizationResult) -> ParetoPosition:
    """Where the baseline (generation 0 = the flown design) sits in the candidate set."""
    baseline = next(c for c in result.candidates if c.generation == 0)
    keys = [o.key for o in result.objectives]
    by_id = {c.id: c for c in result.candidates}

    def vec(cid: str) -> list[float]:
        return [by_id[cid].objective_vector[k] for k in keys]

    dominated_by = [
        fid
        for fid in result.pareto_front_ids
        if fid != baseline.id and dominates(vec(fid), vec(baseline.id))
    ]
    notes = [
        "Objectives (all minimised; science negated): " + ", ".join(keys) + ".",
        "Candidates are catalogue swaps and seeded combinations of the flown design; this is "
        "a local design-space sample, not a global optimum.",
        "Resilient archetype uses the worst-margin proxy (no robustness samples at export).",
    ]
    if not baseline.feasible:
        notes.append("The flown design fails a hard gate, so it cannot be on the front.")
    return ParetoPosition(
        seed=result.seed,
        candidates_evaluated=len(result.candidates),
        front_size=len(result.pareto_front_ids),
        baseline_id=baseline.id,
        baseline_feasible=baseline.feasible,
        baseline_on_front=baseline.id in result.pareto_front_ids,
        dominated_by=dominated_by[:MAX_DOMINATED_BY],
        archetypes=dict(result.archetypes),
        notes=notes,
    )


class ResearchEvidenceService:
    def __init__(
        self,
        graph: GraphService,
        optimization: OptimizationService,
        robustness: RobustnessService,
        schedule: ScheduleService,
        health: HealthMonitorService | None = None,
    ) -> None:
        self._health = health
        self._graph = graph
        self._optimization = optimization
        self._robustness = robustness
        self._schedule = schedule

    def build(
        self, state: MissionState, now: datetime, run: MissionRun | None = None
    ) -> ResearchEvidence:
        not_included: list[str] = []
        stm: list[ScienceTraceRowOut] = []
        mtm: list[MissionTraceRowOut] = []

        g = self._graph.graph(state, now)
        if g.result is not None:
            stm = [
                ScienceTraceRowOut(
                    objective_id=r.objective_id,
                    objective_title=r.objective_title,
                    requirement_id=r.requirement_id,
                    requirement_description=r.requirement_description,
                    capability=r.capability,
                    required=r.required,
                    instrument_ids=list(r.instrument_ids),
                    observation_count=r.observation_count,
                    status=r.status,
                )
                for r in g.result.science_traceability
            ]
            mtm = [
                MissionTraceRowOut(
                    instrument_id=r.instrument_id,
                    instrument_name=r.instrument_name,
                    requirement_ids=list(r.requirement_ids),
                    subsystem_ids=list(r.subsystem_ids),
                    observation_count=r.observation_count,
                )
                for r in g.result.mission_traceability
            ]
        else:
            not_included.append("Traceability matrices: the design could not be analysed.")

        opt = self._optimization.optimize(
            state,
            seed=state.random_seed,
            cap=PASSPORT_PARETO_CANDIDATES,
            robustness_samples=0,
            now=now,
        )
        pareto = pareto_position(opt.result) if opt.result is not None else None
        if pareto is None:
            not_included.append("Pareto position: the design could not be analysed.")

        rob = self._robustness.run(
            state, samples=PASSPORT_ROBUSTNESS_SAMPLES, seed=state.random_seed, now=now
        )
        if rob.result is None:
            not_included.append("Robustness: the design could not be analysed.")

        sched = self._schedule.schedule(state, accept_data_loss=False, now=now)
        if sched.result is None:
            not_included.append("Schedule: the design could not be analysed.")

        health: list[HealthFinding] = []
        if run is not None and self._health is not None:
            report = self._health.monitor(run, now).report
            if report is not None:
                health = report.findings
            else:
                not_included.append("Health monitor: the design could not be analysed.")
        not_included.append(BELIEF_NOTE)
        return ResearchEvidence(
            science_traceability=stm,
            mission_traceability=mtm,
            pareto=pareto,
            robustness=rob.result,
            schedule=sched.result.schedule if sched.result is not None else None,
            health_findings=health,
            not_included=not_included,
        )

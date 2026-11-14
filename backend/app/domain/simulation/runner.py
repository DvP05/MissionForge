"""``run_mission``: SimulationInput -> immutable, reproducible MissionRun (M14, AC-10/11).

Flow: validate the input (analysis matches the design revision and versions) -> launch
gate (an infeasible design is blocked unless ``experimental``) -> rebuild the analysis
context with the engine (``build_context``; no formula is duplicated) -> phase schedule ->
nominal event specs (+ scenario events, Task 4.2) -> ordered events -> telemetry
checkpoints -> science outcomes and final report -> MissionRun.

Reproducible: the result depends only on the SimulationInput, the catalogue, the scenario
inputs, the decisions and the explicitly passed versions. Randomness only via
``prng.make_rng`` (the nominal event set draws nothing).
"""

import hashlib
import json
from collections.abc import Mapping

from app.domain.analysis._params import param_value
from app.domain.analysis.context import AnalysisContext
from app.domain.analysis.orchestrator import ScenarioInputs, build_context
from app.domain.catalog.loader import Catalog
from app.domain.catalog.resolver import resolve_architecture
from app.domain.errors import DomainValidationError
from app.domain.simulation.events import (
    EventSpec,
    build_events,
    downlink_specs,
    maneuver_specs,
    milestone_specs,
    science_specs,
)
from app.domain.simulation.phases import PhaseSchedule, build_schedule
from app.domain.simulation.prng import Rng, make_rng
from app.domain.simulation.report import final_report, return_ratio, science_outcomes
from app.domain.simulation.telemetry import propellant_remaining_fraction, telemetry_samples
from app.schemas.mission import MissionState
from app.schemas.simulation import (
    MissionRun,
    MissionRunManifest,
    PhaseTransition,
    SimulationInput,
)


class LaunchBlocked(DomainValidationError):  # noqa: N818 - name fixed by the task brief
    """Hard constraints failed and the run was not requested as experimental."""

    def __init__(self, failing_constraint_ids: tuple[str, ...]) -> None:
        super().__init__(
            "LAUNCH_BLOCKED",
            "analysis.constraints",
            "launch blocked by failed hard constraints: "
            + ", ".join(failing_constraint_ids)
            + " (fix the design or run it as experimental)",
        )
        self.failing_constraint_ids = failing_constraint_ids


def _validate(sim: SimulationInput, catalog: Catalog) -> None:
    state, analysis = sim.mission_state, sim.analysis
    if (analysis.mission_id, analysis.design_revision) != (
        state.mission_id,
        state.design_revision,
    ):
        raise DomainValidationError(
            "ANALYSIS_REVISION_MISMATCH",
            "analysis.designRevision",
            f"analysis is for {analysis.mission_id} r{analysis.design_revision}, the design is "
            f"{state.mission_id} r{state.design_revision}",
        )
    if analysis.engine_version != sim.engine_version:
        raise DomainValidationError(
            "ENGINE_VERSION_MISMATCH",
            "engineVersion",
            f"analysis engine {analysis.engine_version} != simulation {sim.engine_version}",
        )
    if analysis.catalog_version != sim.catalog_version or catalog.version != sim.catalog_version:
        raise DomainValidationError(
            "CATALOG_VERSION_MISMATCH",
            "catalogVersion",
            f"simulation catalog {sim.catalog_version}, analysis {analysis.catalog_version}, "
            f"loaded {catalog.version}",
        )


def _run_id(sim: SimulationInput, scenario_version: str, decisions: Mapping[str, str]) -> str:
    state = sim.mission_state
    key = [
        state.mission_id,
        state.design_revision,
        sim.random_seed,
        sim.scenario_event_set_id,
        sim.engine_version,
        sim.catalog_version,
        scenario_version,
        sim.experimental,
        sorted(decisions.items()),
    ]
    text = json.dumps(key, separators=(",", ":"), ensure_ascii=True)
    return "run-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


def scenario_event_specs(
    state: MissionState,
    schedule: PhaseSchedule,
    ctx: AnalysisContext,
    rng: Rng,
    event_set_id: str,
) -> list[EventSpec]:
    """Declared scenario events (anomalies, decisions). Task 4.2 injects them here.

    The nominal event set declares none, so nothing is drawn from ``rng``.
    """
    return []


def run_mission(
    sim_input: SimulationInput,
    catalog: Catalog,
    *,
    scenario: ScenarioInputs,
    scenario_version: str,
    app_version: str,
    decisions: Mapping[str, str] | None = None,
) -> MissionRun:
    """Deterministic mission run. ``app_version`` comes from settings, passed in explicitly."""
    _validate(sim_input, catalog)
    state, analysis = sim_input.mission_state, sim_input.analysis
    failing = tuple(c.id for c in analysis.constraints if c.status == "fail")
    if analysis.feasibility == "infeasible" and not sim_input.experimental:
        raise LaunchBlocked(failing)

    ctx = build_context(state, catalog, scenario=scenario)
    resolved = resolve_architecture(state.architecture, catalog)
    adcs = resolved.adcs
    pointing = param_value(adcs, "pointing_accuracy", "deg", field=f"{adcs.id}.pointing_accuracy")
    propellant = analysis.budgets.propellant_mass_kg.value
    per = ctx.maneuvers.per_maneuver
    remaining = propellant_remaining_fraction(ctx, propellant, per[-1][1] if per else 0.0)

    schedule = build_schedule(state)
    rng = make_rng(sim_input.random_seed, "scenario-events", sim_input.scenario_event_set_id)
    specs = [
        *milestone_specs(state, schedule),
        *maneuver_specs(state, schedule, ctx, remaining),
        *science_specs(state, resolved.instruments, ctx),
        *downlink_specs(state, ctx),
        *scenario_event_specs(state, schedule, ctx, rng, sim_input.scenario_event_set_id),
    ]
    events = build_events(specs, schedule)

    chosen = dict(decisions or {})
    decidable = {e.id for e in events if e.choices}
    unknown = sorted(set(chosen) - decidable)
    if unknown:
        raise DomainValidationError(
            "UNKNOWN_DECISION_EVENT",
            "decisions",
            f"no decision event with id {', '.join(unknown)} in this run",
        )

    ratio = return_ratio(ctx)
    outcomes = science_outcomes(state, analysis, ratio)
    telemetry = telemetry_samples(
        state, schedule, ctx, propellant_kg=propellant, pointing_accuracy_deg=pointing
    )
    manifest = MissionRunManifest(
        schema_version=state.schema_version,
        engine_version=sim_input.engine_version,
        catalog_version=sim_input.catalog_version,
        scenario_version=scenario_version,
        event_set_id=sim_input.scenario_event_set_id,
        seed=sim_input.random_seed,
        app_version=app_version,
    )
    return MissionRun(
        run_id=_run_id(sim_input, scenario_version, chosen),
        mission_id=state.mission_id,
        design_revision=state.design_revision,
        seed=sim_input.random_seed,
        scenario_event_set_id=sim_input.scenario_event_set_id,
        engine_version=sim_input.engine_version,
        catalog_version=sim_input.catalog_version,
        experimental=sim_input.experimental,
        input_snapshot=state,
        manifest=manifest,
        phases=tuple(p for p, _ in schedule.transitions),
        phase_transitions=tuple(
            PhaseTransition(phase=p, mission_day=d) for p, d in schedule.transitions
        ),
        events=events,
        telemetry=telemetry,
        decisions=(),
        science_outcomes=outcomes,
        final_report=final_report(
            analysis, outcomes, experimental=sim_input.experimental, ratio=ratio
        ),
    )


__all__ = ["LaunchBlocked", "run_mission", "scenario_event_specs"]

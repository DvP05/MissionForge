"""``run_mission``: SimulationInput -> immutable, reproducible MissionRun (M14, AC-10/11).

Flow: validate the input (analysis matches the design revision and versions; the event
set exists and fits the scenario) -> launch gate (an infeasible design is blocked unless
``experimental``) -> rebuild the analysis context with the engine (``build_context``; no
formula is duplicated) -> phase schedule -> declared anomalies / scenario events that occur
(``anomalies``) -> decisions and effects in event order (``decisions``) -> as-flown plan,
re-analysed by the engine when an effect changed it -> ordered events -> telemetry
checkpoints (with the effect overlay) -> science outcomes and final report -> MissionRun.

Reproducible: the result depends only on the SimulationInput, the catalogue, the scenario
inputs, the event sets, the decisions and the explicitly passed versions. The only
randomness is the declared scenario event days (``make_rng(seed, "scenario", <id>)``,
one stream per declared event).

Early termination (abort choice or depleted battery) is the intended exception to the
"six or more phases" rule (AC-10): the run lists the phases entered up to the termination
day, then ``terminated``; an abort in mid-course therefore shows fewer than six phases, and
the final report is a postmortem so the learning journey continues to the review.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import replace

from app.domain.analysis._params import param_value
from app.domain.analysis.orchestrator import ScenarioInputs, build_context
from app.domain.catalog.loader import Catalog
from app.domain.catalog.resolver import resolve_architecture
from app.domain.errors import DomainValidationError
from app.domain.simulation.anomalies import (
    AnomalyDecl,
    Occurrence,
    ScenarioEventSet,
    evaluate_occurrences,
    resolve_event_set,
)
from app.domain.simulation.decisions import (
    FlownPlan,
    RunState,
    data_losses,
    flown_plan,
    resolve_occurrences,
    returned_bits_after_loss,
)
from app.domain.simulation.events import (
    RANK_EFFECT,
    RANK_SCENARIO,
    RANK_TERMINATION,
    EventSpec,
    build_events,
    downlink_specs,
    maneuver_specs,
    milestone_specs,
    science_specs,
)
from app.domain.simulation.phases import PhaseSchedule, build_schedule
from app.domain.simulation.report import (
    Incident,
    TerminationInfo,
    final_report,
    return_ratio,
    science_outcomes,
)
from app.domain.simulation.telemetry import (
    TelemetryOverlay,
    base_soc,
    propellant_remaining_fraction,
    telemetry_samples,
)
from app.schemas.mission import MissionState
from app.schemas.simulation import (
    EventDecisionMaker,
    MissionRun,
    MissionRunManifest,
    Phase,
    PhaseTransition,
    SimulationInput,
)
from app.schemas.units import Scalar


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


def _state_digest(state: MissionState) -> str:
    """sha256 of the canonical MissionState JSON (R37): content, not just id + revision."""
    canonical = json.dumps(
        state.model_dump(mode="json", by_alias=True),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _run_id(sim: SimulationInput, scenario_version: str, decisions: Mapping[str, str]) -> str:
    """Deterministic run id (R37).

    Key = mission id, design revision, sha256 of the canonical MissionState JSON, seed, event
    set, engine/catalogue/scenario versions, experimental flag and the sorted player
    decisions. The content digest keeps two different designs that share an id + revision
    (e.g. edits in two tabs) from colliding in the run store or the browser run cache.
    """
    state = sim.mission_state
    key = [
        state.mission_id,
        state.design_revision,
        _state_digest(state),
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


def _choice_label(occ: Occurrence, choice_id: str | None) -> str | None:
    return next((c.label for c in occ.decl.choices if c.id == choice_id), None)


def _occurrence_spec(
    occ: Occurrence, run: RunState, chosen: Mapping[str, str], schedule: PhaseSchedule
) -> EventSpec:
    decl = occ.decl
    text = f"{decl.situation} Why this happened: {occ.why}."
    resolved_by: str | None = None
    maker: EventDecisionMaker = "system"
    if decl.choices:
        record = next(r for r in run.records if r.event_id == occ.event_id)
        resolved_by = record.choice_id
        by_player = occ.event_id in chosen
        maker = "player" if by_player else "system"
        chosen_effects = next(c.effects for c in decl.choices if c.id == resolved_by)
        headroom = occ.trigger.get("value")
        if (
            "propellant_delta" in chosen_effects
            and isinstance(decl, AnomalyDecl)
            and decl.rule.kind == "delta-v-shortfall"
            and isinstance(headroom, float)
            and headroom < 0.0
        ):
            text += (
                " Warning: the delta-v headroom is already negative, so the reserve burn "
                "cannot be fully flown; the propellant telemetry is clamped at 0 "
                "(propellant_delta is telemetry-only)."
            )
        options = "; ".join(f"{c.label} ({c.id}): {c.tradeoff}" for c in decl.choices)
        text += (
            f" {decl.prompt} Options: {options}. Chosen: {_choice_label(occ, resolved_by)} "
            f"({'player choice' if by_player else 'default, no player choice'})."
        )
    text += (
        " The effects follow a deterministic design rule."
        if occ.source == "design"
        else " Its day is a seeded scenario uncertainty; the effects are deterministic."
    )
    return EventSpec(
        occ.mission_day, decl.event_type, occ.severity, decl.title, text, occ.trigger,
        RANK_SCENARIO, phase=schedule.phase_at(occ.mission_day),
        choices=decl.contract_choices(), resolved_by=resolved_by,
        decision_maker=maker, id=occ.event_id,
    )  # fmt: skip


def _effect_specs(
    state: MissionState, flown: FlownPlan, by_id: Mapping[str, Occurrence]
) -> list[EventSpec]:
    """Log entries for observations skipped and contacts missed because of an event."""
    ops = state.operations
    out: list[EventSpec] = []
    for i, cause in sorted(flown.skipped_observations.items()):
        item, occ = ops.observation_plan[i], by_id[cause]
        trig: dict[str, Scalar] = {
            "source": occ.source,
            "ref": str(occ.trigger["ref"]),
            "plan_item": f"operations.observationPlan[{i}]",
            "caused_by": cause,
            "measurement_id": item.measurement_id,
        }
        text = (
            f"Observation of {item.measurement_id} planned for day {item.start_day:g} is not "
            f"flown: {occ.decl.title.lower()} (event {cause}) removed it from the timeline."
        )
        out.append(EventSpec(item.start_day, "science", "warning",
                             f"Observation skipped: {item.measurement_id}", text, trig,
                             RANK_EFFECT))  # fmt: skip
    for i, cause in sorted(flown.missed_contacts.items()):
        c, occ = ops.downlink_plan[i], by_id[cause]
        trig = {
            "source": occ.source,
            "ref": str(occ.trigger["ref"]),
            "plan_item": f"operations.downlinkPlan[{i}]",
            "caused_by": cause,
        }
        text = (
            f"The pass planned for day {c.start_day:g} is missed ({occ.decl.title.lower()}, "
            f"event {cause}); its data stays on board for a later contact."
        )
        out.append(EventSpec(c.start_day, "downlink", "warning",
                             f"Ground contact {i + 1} missed", text, trig,
                             RANK_EFFECT))  # fmt: skip
    return out


def _mark_changes(
    specs: list[EventSpec], index: Sequence[int], changed_by: Mapping[int, str], what: str
) -> list[EventSpec]:
    """Tag flown items whose plan an event changed (``caused_by`` + a sentence)."""
    out: list[EventSpec] = []
    for k, spec in zip(index, specs, strict=True):
        cause = changed_by.get(k)
        if cause is None:
            out.append(spec)
            continue
        out.append(
            replace(
                spec,
                trigger={**spec.trigger, "caused_by": cause},
                description=f"{spec.description} The planned {what} was changed by event {cause}.",
            )
        )
    return out


def _termination(
    run: RunState, by_id: Mapping[str, Occurrence], flown: FlownPlan, schedule: PhaseSchedule
) -> tuple[EventSpec, TerminationInfo] | None:
    term = run.terminated
    if term is None:
        return None
    occ = by_id[term.event_id]
    if term.cause == "battery-depleted":
        cause = f"{occ.decl.title}: the battery was depleted (day {term.mission_day:g})"
    else:
        label = _choice_label(occ, term.choice_id)
        cause = f"{occ.decl.title}: the choice '{label}' ended the mission"
    text = (
        f"{cause}. {flown.cancelled_observations} planned observation(s) and "
        f"{flown.cancelled_contacts} planned contact(s) are cancelled. The final report is a "
        "postmortem of what the design lacked; the review stays available."
    )
    trig: dict[str, Scalar] = {
        "source": occ.source,
        "ref": str(occ.trigger["ref"]),
        "caused_by": occ.event_id,
        "cause": term.cause,
        "choice": term.choice_id or "",
    }
    spec = EventSpec(term.mission_day, "milestone", "critical", "Mission terminated", text,
                     trig, RANK_TERMINATION, phase="terminated")  # fmt: skip
    return spec, TerminationInfo(term.mission_day, schedule.phase_at(term.mission_day), cause)


def _transitions(schedule: PhaseSchedule, end: float | None) -> tuple[tuple[Phase, float], ...]:
    if end is None:
        return schedule.transitions
    kept = tuple((p, d) for p, d in schedule.transitions if d <= end and p != "complete")
    return (*kept, ("terminated", end))


def _overlay(
    run: RunState, occurred: tuple[Occurrence, ...], losses: tuple[tuple[float, float, str], ...]
) -> TelemetryOverlay:
    dips: dict[float, float] = {}
    for a in run.applied:
        if "soc_delta" in a.effects:
            dips[a.mission_day] = dips.get(a.mission_day, 0.0) + a.effects["soc_delta"]
    return TelemetryOverlay(
        event_days=tuple(dict.fromkeys(o.mission_day for o in occurred)),
        soc_dips=dips,
        propellant_steps=tuple(
            (a.mission_day, a.effects["propellant_delta"])
            for a in run.applied
            if "propellant_delta" in a.effects
        ),
        buffer_losses=tuple((d, b) for d, b, _ in losses),
        end_day=run.terminated.mission_day if run.terminated is not None else None,
    )


def run_mission(
    sim_input: SimulationInput,
    catalog: Catalog,
    *,
    scenario: ScenarioInputs,
    event_sets: Mapping[str, ScenarioEventSet],
    scenario_version: str,
    app_version: str,
    decisions: Mapping[str, str] | None = None,
) -> MissionRun:
    """Deterministic mission run. ``app_version`` comes from settings, passed in explicitly.

    ``event_sets`` are the loaded ``data/scenarios`` sets (``anomalies.load_event_sets``);
    ``decisions`` maps a decision event id to a choice id (missing: the default choice).
    """
    _validate(sim_input, catalog)
    state, analysis = sim_input.mission_state, sim_input.analysis
    event_set = resolve_event_set(event_sets, sim_input.scenario_event_set_id, state.scenario_id)
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

    # declared events -> decisions and effects (event order) -> as-flown plan
    occurrences = evaluate_occurrences(
        event_set, state, schedule, ctx,
        constraints={c.id: c.status for c in analysis.constraints},
        instruments=resolved.instruments, pointing_deg=pointing, seed=sim_input.random_seed,
    )  # fmt: skip
    chosen = dict(decisions or {})
    decidable = {o.event_id for o in occurrences if o.decl.choices}
    unknown = sorted(set(chosen) - decidable)
    if unknown:
        raise DomainValidationError(
            "UNKNOWN_DECISION_EVENT",
            "decisions",
            f"no decision event with id {', '.join(unknown)} in this run",
        )
    run_state, occurred = resolve_occurrences(
        occurrences, chosen, soc_at=lambda day: base_soc(ctx, schedule.phase_at(day))
    )
    cancelled = sorted(set(chosen) - {o.event_id for o in occurred})
    if cancelled:
        raise DomainValidationError(
            "UNKNOWN_DECISION_EVENT",
            "decisions",
            f"decision event(s) {', '.join(cancelled)} do not happen: the mission ended earlier",
        )
    flown = flown_plan(state, run_state)
    fctx = build_context(flown.state, catalog, scenario=scenario) if flown.changed else ctx
    by_id = {o.event_id: o for o in occurred}
    term = _termination(run_state, by_id, flown, schedule)
    end = run_state.terminated.mission_day if run_state.terminated is not None else None

    nominal_specs = [
        *milestone_specs(state, schedule),
        *maneuver_specs(state, schedule, fctx, remaining),
    ]
    if end is not None:
        nominal_specs = [
            sp for sp in nominal_specs if sp.mission_day <= end and sp.phase != "complete"
        ]
    specs = [
        *nominal_specs,
        *_mark_changes(
            science_specs(flown.state, resolved.instruments, fctx, flown.observation_index),
            flown.observation_index,
            flown.duty_changed_by,
            "duty cycle",
        ),
        *_mark_changes(
            downlink_specs(flown.state, fctx, flown.contact_index),
            flown.contact_index,
            flown.rate_changed_by,
            "rate",
        ),
        *_effect_specs(state, flown, by_id),
        *(_occurrence_spec(o, run_state, chosen, schedule) for o in occurred),
        *((term[0],) if term is not None else ()),
    ]
    events = build_events(specs, schedule)

    ratio = return_ratio(fctx)
    losses = data_losses(run_state, fctx)
    generated = fctx.data.generated_bits
    returned_bits = returned_bits_after_loss(fctx, sum(b for _, b, _ in losses))
    after_loss = returned_bits / generated if generated > 0.0 else 0.0
    scale = after_loss / ratio if ratio > 0.0 else 1.0
    outcomes = science_outcomes(state, fctx.science, ratio, scale)
    telemetry = telemetry_samples(
        flown.state, schedule, fctx, propellant_kg=propellant, pointing_accuracy_deg=pointing,
        overlay=_overlay(run_state, occurred, losses) if occurred else None,
    )  # fmt: skip
    incidents = tuple(
        Incident(
            declared_id=o.decl.id,
            event_type=o.decl.event_type,
            mission_day=o.mission_day,
            title=o.decl.title,
            why=o.why,
            counterfactual=o.decl.counterfactual,
            choice_label=_choice_label(
                o, next((r.choice_id for r in run_state.records if r.event_id == o.event_id), None)
            ),
        )
        for o in occurred
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
    transitions = _transitions(schedule, end)
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
        phases=tuple(p for p, _ in transitions),
        phase_transitions=tuple(PhaseTransition(phase=p, mission_day=d) for p, d in transitions),
        events=events,
        telemetry=telemetry,
        decisions=run_state.records,
        science_outcomes=outcomes,
        final_report=final_report(
            analysis, outcomes, experimental=sim_input.experimental, ratio=ratio,
            science=fctx.science, returned_scale=scale, incidents=incidents,
            termination=term[1] if term is not None else None, nominal=event_set.nominal,
        ),
    )  # fmt: skip


__all__ = ["LaunchBlocked", "run_mission"]

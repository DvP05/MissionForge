"""Typed, explainable mission events with deterministic ordering (architecture 9.2, 9.4).

Generators return ``EventSpec`` records; ``build_events`` sorts them by
``(mission_day, rank, generation order)``, assigns the phase, a global ``sequence``
(tie-break) and a stable id ``f"{phase}-{type}-{n}"`` (n counts per phase and type from 1).

Every trigger names its cause: ``source`` is ``"design"`` (a MissionState value, ``ref``
is its camelCase JSON path) or ``"scenario-event"`` (a declared scenario event, injected
from Task 4.2 on). No event is random or unrelated to the design.

Task 4.2: anomaly / scenario events carry a declared, stable id (``EventSpec.id``:
``anomaly-<id>`` / ``scenario-<id>``) so a player's decision keys do not depend on the
seed; they do not consume the per-(phase, type) counters. Events changed by an effect carry
``caused_by`` (the causing event id) in their trigger. ``science_specs`` / ``downlink_specs``
take the as-flown plan plus ``plan_index`` (the planned index of each flown item) so titles
and ``plan_item`` refs keep the design's numbering.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.domain.analysis.context import AnalysisContext
from app.domain.analysis.science import REASON_NO_CAPABILITY
from app.domain.simulation.phases import (
    COMMISSIONING_DAYS,
    LAUNCH_DEPLOYMENT_DAYS,
    PhaseSchedule,
    time_of_flight_days,
)
from app.schemas.catalog import CatalogComponent
from app.schemas.mission import MissionState
from app.schemas.simulation import (
    DecisionChoice,
    EventDecisionMaker,
    EventSeverity,
    EventType,
    MissionEvent,
    Phase,
)
from app.schemas.units import Scalar

# Same-day ordering: phase transitions, maneuvers, observations, contacts, scenario events
# (anomalies / decisions, Task 4.2), their consequences (skipped / missed items), termination.
RANK_TRANSITION = 0
RANK_MANEUVER = 1
RANK_SCIENCE = 2
RANK_DOWNLINK = 3
RANK_SCENARIO = 4
RANK_EFFECT = 5  # consequences of a same-day scenario-layer event (after its cause)
RANK_TERMINATION = 6


@dataclass(frozen=True)
class EventSpec:
    mission_day: float
    type: EventType
    severity: EventSeverity
    title: str
    description: str
    trigger: Mapping[str, Scalar]
    rank: int
    phase: Phase | None = None  # None: the phase in progress on mission_day
    choices: tuple[DecisionChoice, ...] = ()
    resolved_by: str | None = None
    decision_maker: EventDecisionMaker | None = "system"
    id: str | None = None  # declared stable id (scenario layer); None: phase-type-n scheme


def _design(ref: str, **values: Scalar) -> dict[str, Scalar]:
    return {"source": "design", "ref": ref, **values}


def milestone_specs(state: MissionState, schedule: PhaseSchedule) -> list[EventSpec]:
    arch, ops = state.architecture, state.operations
    tof = time_of_flight_days(state)
    tof_vals: dict[str, Scalar] = {} if tof is None else {"value": tof}
    days = dict(schedule.transitions)
    texts: dict[Phase, tuple[str, str, dict[str, Scalar]]] = {
        "launch-deployment": (
            "Launch and separation",
            f"Launch on {arch.launch_vehicle_id} (departure {state.trajectory.departure_date}). "
            f"Separation and deployment take {days['commissioning']:g} d (gameplay default "
            f"{LAUNCH_DEPLOYMENT_DAYS:g} d).",
            _design("trajectory.departureDate", value=str(state.trajectory.departure_date)),
        ),
        "commissioning": (
            "Commissioning begins",
            f"Bus {arch.bus_id} and its subsystems are checked out before cruise "
            f"({days['cruise'] - days['commissioning']:g} d; gameplay default "
            f"{COMMISSIONING_DAYS:g} d).",
            _design("architecture.busId", value=arch.bus_id),
        ),
        "cruise": (
            "Cruise begins",
            "Transfer toward the target on the selected trajectory "
            f"{state.trajectory.option_id}; arrival on day {schedule.arrival_day:g}.",
            _design("trajectory.timeOfFlightDays", **tof_vals),
        )
        if schedule.transfer
        else (
            "Orbit raising and checkout",
            "No interplanetary transfer on this trajectory: the spacecraft raises and checks "
            f"its orbit for {days['mid-course'] - days['cruise']:g} d (gameplay duration).",
            _design("trajectory.timeOfFlightDays", **tof_vals),
        ),
        "mid-course": (
            "Mid-course phase",
            "Halfway through the cruise (gameplay timing): navigation checks before the "
            f"approach on day {days['approach']:g}.",
            _design("trajectory.timeOfFlightDays", **tof_vals),
        )
        if schedule.transfer
        else (
            "Orbit trim",
            f"Orbit trim and navigation checks for {days['approach'] - days['mid-course']:g} d "
            "(gameplay duration) before the spacecraft settles on its operating orbit.",
            _design("trajectory.timeOfFlightDays", **tof_vals),
        ),
        "approach": (
            "Target approach",
            f"Approach preparation ahead of arrival on day {schedule.arrival_day:g} "
            f"(time of flight); science starts on day {days['science-ops']:g}.",
            _design("trajectory.timeOfFlightDays", **tof_vals),
        )
        if schedule.transfer
        else (
            "Orbit acquisition",
            f"The spacecraft is on its operating orbit from day {schedule.arrival_day:g}; "
            f"instruments are prepared until science starts on day {days['science-ops']:g}.",
            _design("trajectory.timeOfFlightDays", **tof_vals),
        ),
        "science-ops": (
            "Science operations begin",
            f"{len(ops.observation_plan)} planned observation(s) run until day "
            f"{days['downlink-return']:g}; contacts during this phase return data as it is "
            "collected.",
            _design("operations.observationPlan", value=len(ops.observation_plan)),
        ),
        "downlink-return": (
            "Downlink and data return",
            "Observations are complete; remaining contacts return the buffered data until "
            f"the mission ends on day {schedule.end_day:g}.",
            _design("operations.downlinkPlan", value=len(ops.downlink_plan)),
        ),
        "complete": (
            "Mission complete",
            (
                f"The planned mission duration ({ops.mission_duration_days:g} d) has elapsed "
                "and the final report is compiled."
                if schedule.end_day <= ops.mission_duration_days
                else f"The mission ends on day {schedule.end_day:g}, after the planned "
                f"{ops.mission_duration_days:g} d, so the last planned activity completes; "
                "the final report is compiled."
            ),
            _design(
                "operations.missionDurationDays",
                value=ops.mission_duration_days,
                end_day=schedule.end_day,
            ),
        ),
    }
    out: list[EventSpec] = []
    for phase, day in schedule.transitions:
        title, text, trig = texts[phase]
        out.append(EventSpec(day, "milestone", "info", title, text, trig, RANK_TRANSITION, phase))
    return out


def maneuver_specs(
    state: MissionState,
    schedule: PhaseSchedule,
    ctx: AnalysisContext,
    remaining_fraction_after: float,
) -> list[EventSpec]:
    per = ctx.maneuvers.per_maneuver
    if not per:
        return []
    dv_ms = per[-1][1]
    margin = ctx.maneuvers.margin_ms
    severity: EventSeverity = "info" if margin >= 0.0 else "warning"
    if schedule.transfer:
        title = "Arrival maneuver"
        when = f"at arrival (day {schedule.arrival_day:g}, rendezvous / orbit insertion)"
    else:
        title = "Primary maneuver"
        when = f"on reaching the operating orbit (day {schedule.arrival_day:g})"
    text = (
        f"Spacecraft maneuver {when} uses {dv_ms:.0f} m/s of the "
        f"{ctx.maneuvers.available_ms:.0f} m/s available (margin after reserve {margin:.0f} m/s); "
        f"{remaining_fraction_after:.1%} of the propellant remains."
    )
    trig = _design(
        "trajectory.missionDeltaVKmPerS",
        value=dv_ms / 1000.0,
        margin_m_per_s=margin,
    )
    return [
        EventSpec(
            schedule.arrival_day, "milestone", severity, title, text, trig,
            RANK_MANEUVER,
        )
    ]  # fmt: skip


def _observation_problem(
    req_id: str, capable: bool, ctx: AnalysisContext
) -> tuple[str, str] | None:
    """(trigger ref, explanation) when the analysis says this observation's data is lost."""
    reason = dict(ctx.science_missing).get(req_id)
    if not capable or reason == REASON_NO_CAPABILITY:
        return (
            "architecture.instrumentIds",
            "no selected instrument provides this capability, so no data is made.",
        )
    if reason is None:
        return None
    if not ctx.pointing_ok:
        return (
            "architecture.adcsId",
            "the ADCS pointing accuracy does not meet the instrument requirement, so the "
            "analysis credits no usable data.",
        )
    if not ctx.power_ok:
        return (
            "architecture.powerId",
            "the power system cannot supply the instrument load, so the analysis credits no "
            "usable data.",
        )
    return (
        "architecture.communicationsId",
        "data is collected, but the analysis returns none of it to the ground over the "
        "planned contacts.",
    )


def science_specs(
    state: MissionState,
    instruments: Sequence[CatalogComponent],
    ctx: AnalysisContext,
    plan_index: Sequence[int] | None = None,
) -> list[EventSpec]:
    reqs = {r.id: r for o in state.science_objectives for r in o.required_measurements}
    out: list[EventSpec] = []
    for k, item in enumerate(state.operations.observation_plan):
        i = plan_index[k] if plan_index is not None else k
        req = reqs.get(item.measurement_id)
        capable = req is not None and any(
            req.instrument_capability in inst.capabilities for inst in instruments
        )
        base = (
            f"Observation of {item.measurement_id} for {item.duration_hours:g} h at duty cycle "
            f"{item.duty_cycle:g}"
        )
        problem = _observation_problem(item.measurement_id, capable, ctx)
        ref = f"operations.observationPlan[{i}]"
        if problem is None:
            severity: EventSeverity = "info"
            text = f"{base}; data is stored in the onboard buffer until the next contact."
        else:
            severity = "warning"
            ref, why = problem
            text = f"{base}: {why}"
        trig = _design(
            ref,
            plan_item=f"operations.observationPlan[{i}]",
            measurement_id=item.measurement_id,
            duration_hours=item.duration_hours,
            duty_cycle=item.duty_cycle,
        )
        out.append(
            EventSpec(
                item.start_day, "science", severity, f"Observation: {item.measurement_id}",
                text, trig, RANK_SCIENCE,
            )
        )  # fmt: skip
    return out


def downlink_specs(
    state: MissionState, ctx: AnalysisContext, plan_index: Sequence[int] | None = None
) -> list[EventSpec]:
    plan = state.operations.downlink_plan
    # the data ledger reports contacts sorted (stably) by start time
    order = sorted(range(len(plan)), key=lambda k: plan[k].start_day)
    results = {k: ctx.data.per_contact[j] for j, k in enumerate(order)}
    out: list[EventSpec] = []
    for k, item in enumerate(plan):
        i = plan_index[k] if plan_index is not None else k
        margin = ctx.contact_links[k].margin_db
        res = results[k]
        if res.rate_bps > 0.0:
            severity: EventSeverity = "info"
            ref = f"operations.downlinkPlan[{i}]"
            text = (
                f"Contact of {item.duration_minutes:g} min at {res.rate_bps / 1000.0:g} kbit/s "
                f"(link margin {margin:+.2f} dB) returns {res.downlinked_bits / 1e6:.1f} Mbit."
            )
        else:
            severity = "warning"
            ref = "architecture.communicationsId"
            text = (
                f"The link does not close (margin {margin:+.2f} dB at the contact rate with "
                f"{state.architecture.communications_id}): this contact returns no data and "
                "the collected data stays on board."
            )
        trig = _design(
            ref,
            plan_item=f"operations.downlinkPlan[{i}]",
            link_margin_db=margin,
            rate_bps=res.rate_bps,
            returned_bits=res.downlinked_bits,
        )
        out.append(
            EventSpec(
                item.start_day, "downlink", severity, f"Ground contact {i + 1}", text, trig,
                RANK_DOWNLINK,
            )
        )  # fmt: skip
    return out


def build_events(specs: Sequence[EventSpec], schedule: PhaseSchedule) -> tuple[MissionEvent, ...]:
    ordered = sorted(enumerate(specs), key=lambda p: (p[1].mission_day, p[1].rank, p[0]))
    counters: dict[tuple[str, str], int] = {}
    out: list[MissionEvent] = []
    for seq, (_, s) in enumerate(ordered):
        phase = s.phase if s.phase is not None else schedule.phase_at(s.mission_day)
        if s.id is None:
            n = counters.get((phase, s.type), 0) + 1
            counters[(phase, s.type)] = n
        out.append(
            MissionEvent(
                id=s.id if s.id is not None else f"{phase}-{s.type}-{n}",
                sequence=seq,
                mission_day=s.mission_day,
                phase=phase,
                type=s.type,
                severity=s.severity,
                title=s.title,
                description=s.description,
                trigger=dict(s.trigger),
                choices=s.choices,
                resolved_by=s.resolved_by,
                decision_maker=s.decision_maker,
            )
        )
    return tuple(out)


__all__ = [
    "RANK_DOWNLINK",
    "RANK_EFFECT",
    "RANK_MANEUVER",
    "RANK_SCENARIO",
    "RANK_SCIENCE",
    "RANK_TERMINATION",
    "RANK_TRANSITION",
    "EventSpec",
    "build_events",
    "downlink_specs",
    "maneuver_specs",
    "milestone_specs",
    "science_specs",
]

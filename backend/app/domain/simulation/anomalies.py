"""Scenario event sets and design-traced anomaly rules (architecture 9.4, M14; Task 4.2).

Event-set files (``data/scenarios/*.events.json``, camelCase JSON; loaded from an explicit
directory, never from the environment)::

    {
      "eventSetId": "neo-default-v1", "version": "0.1.0", "title": "...",
      "scenarioIds": ["neo-rendezvous"],        # [] = applies to every scenario
      "default": true,                          # the scenario's default set (one per scenario)
      "extends": "generic-design-v1",           # optional: inherit that set's declarations
      "assumptions": ["..."],
      "anomalies": [AnomalyDecl, ...],          # design-traced rules
      "scenarioEvents": [ScenarioEventDecl, ...]
    }

``AnomalyDecl``: ``id``, ``title``, ``severity``, ``eventType`` (default ``anomaly``),
``rule`` ``{kind, severityThreshold, unit}``, ``situation``, ``prompt``,
``counterfactual``, ``effects`` (applied whatever is chosen) and 0 or 2-3 ``choices``
``{id, label, tradeoff, effects}``. The FIRST choice is the default (the safest; it must
not terminate the mission). ``ScenarioEventDecl`` is the same with ``window`` instead of
``rule``.

Design anomalies tell the same story as the analysis (R31): a rule fires ONLY when its
analysis gate is open, i.e. the corresponding hard/soft constraint is ``warning`` or
``fail`` (or, for pointing, the analysis' ``pointing_ok`` is false). A design whose analysis
raises none of these sees no design anomaly (no random punishment). ``severityThreshold``
is a secondary, labelled gameplay selector only: the event is ``critical`` when a gating
constraint fails or the value is beyond the threshold, otherwise the declared severity.

======================  ========================================  ============  ==========
rule kind               gate (analysis)                           value / unit  event day
======================  ========================================  ============  ==========
data-return-shortfall   ``link-margin`` or ``data-return`` warn   worst link    first
                        or fail                                   margin, dB    contact
battery-reserve-low     ``battery-reserve`` or ``energy-closure``  min SoC -      first
                        warn or fail                              floor         observation
pointing-out-of-spec    ``AnalysisContext.pointing_ok`` false      ADCS acc. /   first
                                                                  tightest req. observation
delta-v-shortfall       ``delta-v-margin`` warn or fail           margin /      mid-course
                                                                  available     start
======================  ========================================  ============  ==========

(``data-return`` reflects the link and contact plan; ``battery-reserve`` / ``energy-closure``
the power ledger.) Refs: ``architecture.communicationsId`` / ``powerId`` / ``adcsId`` /
``propulsionId``.

Scenario events (``window``): the occurrence day is uniform in the window, drawn from
``make_rng(seed, "scenario", <event id>)`` (one independent stream per declared event) and
rounded to 0.001 d. Windows: ``science-ops`` = [first observation start, last observation
start]; ``contacts`` = [first contact start, last contact start]; ``approach`` = approach
phase start .. science-ops start. An empty plan falls back to the science-ops /
downlink-return phase. These draws are the ONLY randomness of a run.

Effects vocabulary (``EFFECT_KEYS``; ``DecisionChoice.effects`` uses the same keys, float
values, applied from the event day in event order by ``decisions``):

* ``science_time_lost_days`` (day): observations starting in [day, day + v) are not flown.
* ``link_outage_days`` (day): contacts starting in [day, day + v) are missed.
* ``downlink_rate_factor`` (fraction, > 0): contacts starting on/after the day are planned
  at rate x v (the engine recomputes margin and returned data).
* ``duty_cycle_factor`` (0.1..2): observations starting on/after the day run at duty cycle
  x v (capped at 1); the engine recomputes generated data and coverage.
* ``buffer_loss_fraction`` (fraction): that share of the onboard buffer on the day is lost.
* ``soc_delta`` (fraction): battery state of charge change at the event checkpoint
  (recovers at the next checkpoint); a result <= 0 depletes the battery and terminates.
* ``propellant_delta`` (fraction of the loaded propellant): TELEMETRY-ONLY, applied to the
  propellant channel from the day on (clamped at 0); it does not change the maneuver budget.
* ``terminate`` (1 = yes): the mission ends on the event day (phase ``terminated``).
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pydantic.alias_generators import to_camel

from app.domain.analysis.context import AnalysisContext
from app.domain.errors import DomainValidationError
from app.domain.simulation.phases import PhaseSchedule
from app.domain.simulation.prng import make_rng
from app.schemas.catalog import CatalogComponent
from app.schemas.mission import MissionState
from app.schemas.simulation import DecisionChoice, EventSeverity
from app.schemas.units import Scalar

# key -> (min, max, unit) accepted in event-set files
EFFECT_KEYS: dict[str, tuple[float, float, str]] = {
    "science_time_lost_days": (0.0, 3650.0, "day"),
    "link_outage_days": (0.0, 3650.0, "day"),
    "downlink_rate_factor": (0.01, 1.0, "fraction"),
    "duty_cycle_factor": (0.1, 2.0, "ratio"),
    "buffer_loss_fraction": (0.0, 1.0, "fraction"),
    "soc_delta": (-1.0, 1.0, "fraction"),
    "propellant_delta": (-1.0, 1.0, "fraction"),
    "terminate": (0.0, 1.0, "flag"),
}

RuleKind = Literal[
    "data-return-shortfall",
    "battery-reserve-low",
    "pointing-out-of-spec",
    "delta-v-shortfall",
]
RULE_UNITS: dict[str, str] = {
    "data-return-shortfall": "dB",
    "battery-reserve-low": "fraction",
    "pointing-out-of-spec": "fraction",
    "delta-v-shortfall": "fraction",
}
# analysis constraints that open each rule's gate (warning or fail)
RULE_GATES: dict[str, tuple[str, ...]] = {
    "data-return-shortfall": ("link-margin", "data-return"),
    "battery-reserve-low": ("battery-reserve", "energy-closure"),
    "pointing-out-of-spec": (),  # gated by AnalysisContext.pointing_ok
    "delta-v-shortfall": ("delta-v-margin",),
}
OPEN_STATUSES = ("warning", "fail")
Window = Literal["science-ops", "contacts", "approach"]
SCENARIO_DAY_DECIMALS = 3
NO_HEADROOM = -1.0  # headroom reported when no delta-v is available at all


class _Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, extra="forbid", frozen=True)


def _check_effects(effects: Mapping[str, float], where: str) -> None:
    for key, value in effects.items():
        if key not in EFFECT_KEYS:
            raise ValueError(f"{where}: unknown effect {key!r} (allowed: {sorted(EFFECT_KEYS)})")
        lo, hi, _ = EFFECT_KEYS[key]
        if not lo <= value <= hi:
            raise ValueError(f"{where}: effect {key}={value} outside [{lo}, {hi}]")


class ChoiceDecl(_Model):
    id: str = Field(min_length=1)
    label: str
    tradeoff: str = Field(min_length=1)
    effects: dict[str, float] = Field(default_factory=dict)

    def contract(self) -> DecisionChoice:
        return DecisionChoice(
            id=self.id, label=self.label, tradeoff=self.tradeoff, effects=dict(self.effects)
        )


class RuleDecl(_Model):
    kind: RuleKind
    severity_threshold: float  # gameplay severity selector (not the trigger)
    unit: Literal["dB", "fraction"]

    @model_validator(mode="after")
    def _unit(self) -> Self:
        if RULE_UNITS[self.kind] != self.unit:
            raise ValueError(f"rule {self.kind} takes unit {RULE_UNITS[self.kind]}")
        return self


class _EventDecl(_Model):
    id: str = Field(min_length=1, pattern=r"^[a-z0-9-]+$")
    title: str
    severity: EventSeverity
    event_type: Literal["anomaly", "decision"] = "anomaly"
    situation: str
    prompt: str | None = None
    counterfactual: str
    effects: dict[str, float] = Field(default_factory=dict)
    choices: tuple[ChoiceDecl, ...] = ()

    @model_validator(mode="after")
    def _choices(self) -> Self:
        _check_effects(self.effects, self.id)
        if self.choices and not 2 <= len(self.choices) <= 3:
            raise ValueError(f"{self.id}: a decision needs 2-3 choices")
        ids = [c.id for c in self.choices]
        if len(set(ids)) != len(ids):
            raise ValueError(f"{self.id}: duplicate choice ids")
        for c in self.choices:
            _check_effects(c.effects, f"{self.id}.{c.id}")
        if self.choices and self.choices[0].effects.get("terminate", 0.0) > 0.0:
            raise ValueError(f"{self.id}: the default (first) choice must not terminate")
        if self.choices and self.prompt is None:
            raise ValueError(f"{self.id}: a decision needs a prompt")
        return self

    def contract_choices(self) -> tuple[DecisionChoice, ...]:
        return tuple(c.contract() for c in self.choices)


class AnomalyDecl(_EventDecl):
    rule: RuleDecl


class ScenarioEventDecl(_EventDecl):
    window: Window


class _EventSetFile(_Model):
    event_set_id: str = Field(min_length=1)
    version: str
    title: str
    scenario_ids: tuple[str, ...] = ()
    default: bool = False
    extends: str | None = None
    assumptions: tuple[str, ...] = ()
    anomalies: tuple[AnomalyDecl, ...] = ()
    scenario_events: tuple[ScenarioEventDecl, ...] = ()


@dataclass(frozen=True)
class ScenarioEventSet:
    """A resolved event set (``extends`` merged: inherited declarations first)."""

    id: str
    version: str
    title: str
    scenario_ids: tuple[str, ...]
    assumptions: tuple[str, ...]
    anomalies: tuple[AnomalyDecl, ...]
    scenario_events: tuple[ScenarioEventDecl, ...]
    default: bool = False

    @property
    def nominal(self) -> bool:
        return not self.anomalies and not self.scenario_events


def _invalid(field: str, message: str) -> DomainValidationError:
    return DomainValidationError("EVENT_SET_INVALID", field, message)


def load_event_sets(directory: Path) -> dict[str, ScenarioEventSet]:
    """All ``*.events.json`` sets in ``directory`` keyed by event-set id."""
    raw: dict[str, _EventSetFile] = {}
    for path in sorted(directory.glob("*.events.json")):
        try:
            parsed = _EventSetFile.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (ValidationError, ValueError) as exc:
            raise _invalid(path.name, str(exc)) from exc
        if parsed.event_set_id in raw:
            raise _invalid(path.name, f"duplicate event set id {parsed.event_set_id!r}")
        raw[parsed.event_set_id] = parsed
    out: dict[str, ScenarioEventSet] = {}
    for sid, f in raw.items():
        anomalies, events, assumptions = f.anomalies, f.scenario_events, f.assumptions
        if f.extends is not None:
            base = raw.get(f.extends)
            if base is None or base.extends is not None:
                raise _invalid(sid, f"extends unknown or nested event set {f.extends!r}")
            anomalies = (*base.anomalies, *anomalies)
            events = (*base.scenario_events, *events)
            assumptions = (*base.assumptions, *assumptions)
        ids = [d.id for d in (*anomalies, *events)]
        if len(set(ids)) != len(ids):
            raise _invalid(sid, "duplicate declaration ids")
        if f.default and not f.scenario_ids:
            raise _invalid(sid, "a default event set must name its scenarioIds")
        out[sid] = ScenarioEventSet(
            sid, f.version, f.title, f.scenario_ids, assumptions, anomalies, events, f.default
        )
    for scenario in sorted({s for es in out.values() if es.default for s in es.scenario_ids}):
        defaults = [es.id for es in out.values() if es.default and scenario in es.scenario_ids]
        if len(defaults) > 1:
            raise _invalid(scenario, f"several default event sets: {', '.join(defaults)}")
    return out


def default_event_set_id(scenario_id: str, event_sets: Mapping[str, ScenarioEventSet]) -> str:
    """The event set marked ``"default": true`` for ``scenario_id`` (Task 4.3 picks it)."""
    for es in event_sets.values():
        if es.default and scenario_id in es.scenario_ids:
            return es.id
    raise DomainValidationError(
        "NO_DEFAULT_EVENT_SET", "scenarioId", f"no default event set for {scenario_id!r}"
    )


def resolve_event_set(
    sets: Mapping[str, ScenarioEventSet], event_set_id: str, scenario_id: str
) -> ScenarioEventSet:
    found = sets.get(event_set_id)
    if found is None:
        raise DomainValidationError(
            "UNKNOWN_EVENT_SET",
            "scenarioEventSetId",
            f"unknown scenario event set {event_set_id!r} (known: {', '.join(sorted(sets))})",
        )
    if found.scenario_ids and scenario_id not in found.scenario_ids:
        raise DomainValidationError(
            "EVENT_SET_SCENARIO_MISMATCH",
            "scenarioEventSetId",
            f"event set {event_set_id!r} is for {', '.join(found.scenario_ids)}, not {scenario_id}",
        )
    return found


@dataclass(frozen=True)
class Occurrence:
    """A declared event that occurs in this run (before any decision is applied)."""

    event_id: str  # "anomaly-<id>" or "scenario-<id>" (stable across seeds and decisions)
    decl: AnomalyDecl | ScenarioEventDecl
    mission_day: float
    source: Literal["design", "scenario-event"]
    trigger: Mapping[str, Scalar]
    why: str  # "why this happened", with the analysis finding and the current value
    severity: EventSeverity


@dataclass(frozen=True)
class _Gate:
    open: bool
    failed: bool
    statuses: dict[str, str]

    def text(self) -> str:
        return ", ".join(f"{k} {v}" for k, v in self.statuses.items())


def _gate(kind: str, constraints: Mapping[str, str]) -> _Gate:
    statuses = {c: constraints[c] for c in RULE_GATES[kind] if constraints.get(c) in OPEN_STATUSES}
    return _Gate(bool(statuses), "fail" in statuses.values(), statuses)


def _first_observation_day(state: MissionState) -> float | None:
    plan = state.operations.observation_plan
    return min(o.start_day for o in plan) if plan else None


def _data_rule(
    decl: AnomalyDecl, state: MissionState, ctx: AnalysisContext, gate: _Gate
) -> Occurrence | None:
    plan = state.operations.downlink_plan
    if not gate.open or not plan:
        return None
    first = min(range(len(plan)), key=lambda k: (plan[k].start_day, k))
    worst = min(lk.margin_db for lk in ctx.contact_links)
    thr = decl.rule.severity_threshold
    trig: dict[str, Scalar] = {
        "ref": "architecture.communicationsId",
        "plan_item": f"operations.downlinkPlan[{first}]",
        "value_db": worst,
        "severity_threshold_db": thr,
        **{f"constraint_{k}": v for k, v in gate.statuses.items()},
    }
    why = (
        f"the analysis flags the downlink ({gate.text()}): with "
        f"{state.architecture.communications_id} the worst link margin is {worst:+.2f} dB and "
        "the contact plan has no slack, so a lost pass turns into a backlog"
    )
    return _occ(decl, plan[first].start_day, trig, why, gate.failed or worst < thr)


def _battery_rule(
    decl: AnomalyDecl,
    state: MissionState,
    schedule: PhaseSchedule,
    ctx: AnalysisContext,
    gate: _Gate,
) -> Occurrence | None:
    if not gate.open:
        return None
    reserve = ctx.energy.min_soc_fraction - ctx.energy.soc_floor_fraction
    thr = decl.rule.severity_threshold
    day = _first_observation_day(state)
    trig: dict[str, Scalar] = {
        "ref": "architecture.powerId",
        "value": reserve,
        "severity_threshold": thr,
        "min_soc_fraction": ctx.energy.min_soc_fraction,
        "soc_floor_fraction": ctx.energy.soc_floor_fraction,
        **{f"constraint_{k}": v for k, v in gate.statuses.items()},
    }
    why = (
        f"the analysis flags the power system ({gate.text()}): the worst power cycle of "
        f"{state.architecture.power_id} ends at {ctx.energy.min_soc_fraction:.0%} state of "
        f"charge against a {ctx.energy.soc_floor_fraction:.0%} reserve floor"
    )
    when = day if day is not None else schedule.start_of("science-ops")
    return _occ(decl, when, trig, why, gate.failed or reserve < thr)


def _pointing_rule(
    decl: AnomalyDecl,
    state: MissionState,
    ctx: AnalysisContext,
    instruments: Sequence[CatalogComponent],
    pointing_deg: float,
) -> Occurrence | None:
    reqs = [
        (i.parameters["pointing_requirement"].value, i.id)
        for i in instruments
        if "pointing_requirement" in i.parameters
        and i.parameters["pointing_requirement"].value > 0.0
    ]
    day = _first_observation_day(state)
    if ctx.pointing_ok or not reqs or day is None:
        return None
    tightest, inst = min(reqs)
    ratio = pointing_deg / tightest
    thr = decl.rule.severity_threshold
    trig: dict[str, Scalar] = {
        "ref": "architecture.adcsId",
        "value": ratio,
        "severity_threshold": thr,
        "pointing_accuracy_deg": pointing_deg,
        "requirement_deg": tightest,
        "instrument": inst,
        "analysis_pointing_ok": False,
    }
    why = (
        f"the analysis finds the pointing out of spec: {state.architecture.adcs_id} points to "
        f"{pointing_deg:g} deg, {ratio:.2f} x the {tightest:g} deg requirement of {inst}"
    )
    return _occ(decl, day, trig, why, ratio > thr)


def _propellant_rule(
    decl: AnomalyDecl,
    state: MissionState,
    schedule: PhaseSchedule,
    ctx: AnalysisContext,
    gate: _Gate,
) -> Occurrence | None:
    if not gate.open:
        return None
    budget = ctx.maneuvers
    headroom = budget.margin_ms / budget.available_ms if budget.available_ms > 0 else NO_HEADROOM
    thr = decl.rule.severity_threshold
    trig: dict[str, Scalar] = {
        "ref": "architecture.propulsionId",
        "value": headroom,
        "severity_threshold": thr,
        "margin_m_per_s": budget.margin_ms,
        "available_m_per_s": budget.available_ms,
        **{f"constraint_{k}": v for k, v in gate.statuses.items()},
    }
    why = (
        f"the analysis flags the delta-v budget ({gate.text()}): "
        f"{state.architecture.propulsion_id} leaves {budget.margin_ms:.0f} m/s of "
        f"{budget.available_ms:.0f} m/s available after the planned maneuvers and reserve "
        f"({headroom:.0%} headroom)"
    )
    return _occ(decl, schedule.start_of("mid-course"), trig, why, gate.failed or headroom < thr)


def _occ(
    decl: AnomalyDecl, day: float, trig: Mapping[str, Scalar], why: str, escalate: bool
) -> Occurrence:
    full: dict[str, Scalar] = {
        "source": "design",
        **trig,
        "rule": decl.rule.kind,
        "anomaly": decl.id,
    }
    severity: EventSeverity = "critical" if escalate else decl.severity
    return Occurrence(f"anomaly-{decl.id}", decl, day, "design", full, why, severity)


def _window(window: Window, state: MissionState, schedule: PhaseSchedule) -> tuple[float, float]:
    ops = state.operations
    if window == "science-ops" and ops.observation_plan:
        days = [o.start_day for o in ops.observation_plan]
        return min(days), max(days)
    if window == "contacts" and ops.downlink_plan:
        days = [c.start_day for c in ops.downlink_plan]
        return min(days), max(days)
    if window == "approach":
        return schedule.start_of("approach"), schedule.start_of("science-ops")
    if window == "contacts":
        return schedule.start_of("downlink-return"), schedule.end_day
    return schedule.start_of("science-ops"), schedule.start_of("downlink-return")


def _scenario_occurrence(
    decl: ScenarioEventDecl,
    event_set: ScenarioEventSet,
    state: MissionState,
    schedule: PhaseSchedule,
    seed: int,
) -> Occurrence:
    lo, hi = _window(decl.window, state, schedule)
    rng = make_rng(seed, "scenario", decl.id)
    day = round(lo + rng.random() * (hi - lo), SCENARIO_DAY_DECIMALS)
    trig: dict[str, Scalar] = {
        "source": "scenario-event",
        "ref": f"scenarioEvents/{event_set.id}/{decl.id}",
        "rule": "seeded-day",
        "window": decl.window,
        "window_start_day": lo,
        "window_end_day": hi,
        "stream": f"make_rng(seed, 'scenario', '{decl.id}')",
    }
    why = (
        f"the event set {event_set.id} declares this scenario event in the {decl.window} "
        f"window (days {lo:g}-{hi:g}); its day is drawn from the seeded scenario stream"
    )
    return Occurrence(f"scenario-{decl.id}", decl, day, "scenario-event", trig, why, decl.severity)


def evaluate_occurrences(
    event_set: ScenarioEventSet,
    state: MissionState,
    schedule: PhaseSchedule,
    ctx: AnalysisContext,
    *,
    constraints: Mapping[str, str],
    instruments: Sequence[CatalogComponent],
    pointing_deg: float,
    seed: int,
) -> list[Occurrence]:
    """Declared events that occur, ordered by (day, declaration order).

    ``constraints`` maps analysis constraint id -> status (the analysis gate, R31).
    """
    found: list[Occurrence | None] = []
    for decl in event_set.anomalies:
        kind = decl.rule.kind
        gate = _gate(kind, constraints)
        if kind == "data-return-shortfall":
            found.append(_data_rule(decl, state, ctx, gate))
        elif kind == "battery-reserve-low":
            found.append(_battery_rule(decl, state, schedule, ctx, gate))
        elif kind == "pointing-out-of-spec":
            found.append(_pointing_rule(decl, state, ctx, instruments, pointing_deg))
        else:
            found.append(_propellant_rule(decl, state, schedule, ctx, gate))
    for sdecl in event_set.scenario_events:
        found.append(_scenario_occurrence(sdecl, event_set, state, schedule, seed))
    occs = [o for o in found if o is not None]
    return [o for _, o in sorted(enumerate(occs), key=lambda p: (p[1].mission_day, p[0]))]


__all__ = [
    "EFFECT_KEYS",
    "RULE_GATES",
    "AnomalyDecl",
    "ChoiceDecl",
    "Occurrence",
    "RuleDecl",
    "ScenarioEventDecl",
    "ScenarioEventSet",
    "default_event_set_id",
    "evaluate_occurrences",
    "load_event_sets",
    "resolve_event_set",
]

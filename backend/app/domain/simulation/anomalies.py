"""Scenario event sets and design-traced anomaly rules (architecture 9.4, M14; Task 4.2).

Event-set files (``data/scenarios/*.events.json``, camelCase JSON; loaded from an explicit
directory, never from the environment)::

    {
      "eventSetId": "neo-default-v1", "version": "0.1.0", "title": "...",
      "scenarioIds": ["neo-rendezvous"],        # [] = applies to every scenario
      "extends": "generic-design-v1",           # optional: inherit that set's declarations
      "assumptions": ["..."],
      "anomalies": [AnomalyDecl, ...],          # design-traced rules
      "scenarioEvents": [ScenarioEventDecl]     # at most one declared scenario event
    }

``AnomalyDecl``: ``id``, ``title``, ``severity``, ``eventType`` (default ``anomaly``),
``rule`` ``{kind, threshold, unit}``, ``situation``, ``prompt``, ``counterfactual``,
``effects`` (applied whatever is chosen) and 0 or 2-3 ``choices``
``{id, label, tradeoff, effects}``. The FIRST choice is the default (the safest; it must
not terminate the mission). ``ScenarioEventDecl`` is the same with ``window`` instead of
``rule``.

Rule kinds (closed set; thresholds come from the file, values from the analysis context):

* ``link-margin-below`` (dB): the first planned contact (by start day) whose link margin
  at the reference range and capped rate is below the threshold -> event on that
  contact's start day, ``ref`` ``architecture.communicationsId``.
* ``battery-reserve-below`` (fraction): worst end-of-cycle state of charge minus the SoC
  floor of the energy ledger below the threshold -> event at the first observation start
  (science power cycle), ``ref`` ``architecture.powerId``.
* ``pointing-ratio-above`` (fraction): ADCS pointing accuracy / tightest pointing
  requirement of the selected instruments above the threshold -> event at the first
  observation start, ``ref`` ``architecture.adcsId``.
* ``propellant-headroom-below`` (fraction): delta-v margin after the planned maneuvers and
  reserve / available delta-v below the threshold (no available delta-v counts as -1)
  -> event at the start of mid-course, ``ref`` ``architecture.propulsionId``.

Scenario events (``window`` ``science-ops``): the occurrence day is uniform in
[first observation start, last observation start] (science-ops phase when nothing is
observed), drawn from ``make_rng(seed, "scenario", <event id>)`` and rounded to 0.001 d.
This is the ONLY randomness of a run; every effect is deterministic.

Effects vocabulary (``EFFECT_KEYS``; ``DecisionChoice.effects`` uses the same keys, float
values, applied from the event day in event order by ``decisions``):

* ``science_time_lost_days`` (day): observations starting in [day, day + v) are not flown.
* ``link_outage_days`` (day): contacts starting in [day, day + v) are missed.
* ``downlink_rate_factor`` (fraction, > 0): contacts starting on/after the day are planned
  at rate x v (the engine recomputes margin and returned data).
* ``buffer_loss_fraction`` (fraction): that share of the onboard buffer on the day is lost.
* ``soc_delta`` (fraction): battery state of charge change at the event checkpoint
  (recovers at the next checkpoint); a result <= 0 depletes the battery and terminates.
* ``propellant_delta`` (fraction of the loaded propellant): applied from the day on.
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
    "buffer_loss_fraction": (0.0, 1.0, "fraction"),
    "soc_delta": (-1.0, 1.0, "fraction"),
    "propellant_delta": (-1.0, 1.0, "fraction"),
    "terminate": (0.0, 1.0, "flag"),
}

RuleKind = Literal[
    "link-margin-below",
    "battery-reserve-below",
    "pointing-ratio-above",
    "propellant-headroom-below",
]
RULE_UNITS: dict[str, str] = {
    "link-margin-below": "dB",
    "battery-reserve-below": "fraction",
    "pointing-ratio-above": "fraction",
    "propellant-headroom-below": "fraction",
}
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
    threshold: float
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
    window: Literal["science-ops"]


class _EventSetFile(_Model):
    event_set_id: str = Field(min_length=1)
    version: str
    title: str
    scenario_ids: tuple[str, ...] = ()
    extends: str | None = None
    assumptions: tuple[str, ...] = ()
    anomalies: tuple[AnomalyDecl, ...] = ()
    scenario_events: tuple[ScenarioEventDecl, ...] = Field(default=(), max_length=1)


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
        if len(set(ids)) != len(ids) or len(events) > 1:
            raise _invalid(sid, "duplicate declarations or more than one scenario event")
        out[sid] = ScenarioEventSet(
            sid, f.version, f.title, f.scenario_ids, assumptions, anomalies, events
        )
    return out


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
    why: str  # "why this happened", with the current value and the threshold


def _first_observation_day(state: MissionState) -> float | None:
    plan = state.operations.observation_plan
    return min(o.start_day for o in plan) if plan else None


def _link_rule(decl: AnomalyDecl, state: MissionState, ctx: AnalysisContext) -> Occurrence | None:
    plan = state.operations.downlink_plan
    thr = decl.rule.threshold
    for i in sorted(range(len(plan)), key=lambda k: plan[k].start_day):
        margin = ctx.contact_links[i].margin_db
        if margin < thr:
            trig: dict[str, Scalar] = {
                "ref": "architecture.communicationsId",
                "plan_item": f"operations.downlinkPlan[{i}]",
                "value_db": margin,
                "threshold_db": thr,
            }
            why = (
                f"contact {i + 1} has a link margin of {margin:+.2f} dB with "
                f"{state.architecture.communications_id}, below the {thr:g} dB the event set "
                "needs to ride out a fade"
            )
            return _occ(decl, plan[i].start_day, trig, why)
    return None


def _battery_rule(
    decl: AnomalyDecl, state: MissionState, ctx: AnalysisContext
) -> Occurrence | None:
    reserve = ctx.energy.min_soc_fraction - ctx.energy.soc_floor_fraction
    thr = decl.rule.threshold
    day = _first_observation_day(state)
    if reserve >= thr or day is None:
        return None
    trig: dict[str, Scalar] = {
        "ref": "architecture.powerId",
        "value": reserve,
        "threshold": thr,
        "min_soc_fraction": ctx.energy.min_soc_fraction,
        "soc_floor_fraction": ctx.energy.soc_floor_fraction,
    }
    why = (
        f"the worst power cycle of {state.architecture.power_id} ends at "
        f"{ctx.energy.min_soc_fraction:.0%} state of charge, {reserve:+.0%} from the "
        f"{ctx.energy.soc_floor_fraction:.0%} reserve floor (threshold {thr:+.0%})"
    )
    return _occ(decl, day, trig, why)


def _pointing_rule(
    decl: AnomalyDecl,
    state: MissionState,
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
    if not reqs or day is None:
        return None
    tightest, inst = min(reqs)
    ratio = pointing_deg / tightest
    thr = decl.rule.threshold
    if ratio <= thr:
        return None
    trig: dict[str, Scalar] = {
        "ref": "architecture.adcsId",
        "value": ratio,
        "threshold": thr,
        "pointing_accuracy_deg": pointing_deg,
        "requirement_deg": tightest,
        "instrument": inst,
    }
    why = (
        f"{state.architecture.adcs_id} points to {pointing_deg:g} deg, {ratio:.2f} x the "
        f"{tightest:g} deg requirement of {inst} (threshold {thr:g} x)"
    )
    return _occ(decl, day, trig, why)


def _propellant_rule(
    decl: AnomalyDecl, state: MissionState, schedule: PhaseSchedule, ctx: AnalysisContext
) -> Occurrence | None:
    budget = ctx.maneuvers
    headroom = budget.margin_ms / budget.available_ms if budget.available_ms > 0 else NO_HEADROOM
    thr = decl.rule.threshold
    if headroom >= thr:
        return None
    trig: dict[str, Scalar] = {
        "ref": "architecture.propulsionId",
        "value": headroom,
        "threshold": thr,
        "margin_m_per_s": budget.margin_ms,
        "available_m_per_s": budget.available_ms,
    }
    why = (
        f"{state.architecture.propulsion_id} leaves {budget.margin_ms:.0f} m/s of "
        f"{budget.available_ms:.0f} m/s available after the planned maneuvers and reserve "
        f"({headroom:.0%} headroom, threshold {thr:.0%})"
    )
    return _occ(decl, schedule.start_of("mid-course"), trig, why)


def _occ(decl: AnomalyDecl, day: float, trig: Mapping[str, Scalar], why: str) -> Occurrence:
    full: dict[str, Scalar] = {
        "source": "design",
        **trig,
        "rule": decl.rule.kind,
        "anomaly": decl.id,
    }
    return Occurrence(f"anomaly-{decl.id}", decl, day, "design", full, why)


def _scenario_occurrence(
    decl: ScenarioEventDecl,
    event_set: ScenarioEventSet,
    state: MissionState,
    schedule: PhaseSchedule,
    seed: int,
) -> Occurrence:
    plan = state.operations.observation_plan
    if plan:
        lo, hi = min(o.start_day for o in plan), max(o.start_day for o in plan)
    else:
        lo, hi = schedule.start_of("science-ops"), schedule.start_of("downlink-return")
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
        f"the event set {event_set.id} declares this scenario event inside the science "
        f"window (days {lo:g}-{hi:g}); its day is drawn from the seeded scenario stream"
    )
    return Occurrence(f"scenario-{decl.id}", decl, day, "scenario-event", trig, why)


def evaluate_occurrences(
    event_set: ScenarioEventSet,
    state: MissionState,
    schedule: PhaseSchedule,
    ctx: AnalysisContext,
    *,
    instruments: Sequence[CatalogComponent],
    pointing_deg: float,
    seed: int,
) -> list[Occurrence]:
    """Declared events that occur for this design, ordered by (day, declaration order)."""
    found: list[Occurrence | None] = []
    for decl in event_set.anomalies:
        kind = decl.rule.kind
        if kind == "link-margin-below":
            found.append(_link_rule(decl, state, ctx))
        elif kind == "battery-reserve-below":
            found.append(_battery_rule(decl, state, ctx))
        elif kind == "pointing-ratio-above":
            found.append(_pointing_rule(decl, state, instruments, pointing_deg))
        else:
            found.append(_propellant_rule(decl, state, schedule, ctx))
    for sdecl in event_set.scenario_events:
        found.append(_scenario_occurrence(sdecl, event_set, state, schedule, seed))
    occs = [o for o in found if o is not None]
    return [o for _, o in sorted(enumerate(occs), key=lambda p: (p[1].mission_day, p[0]))]


__all__ = [
    "EFFECT_KEYS",
    "AnomalyDecl",
    "ChoiceDecl",
    "Occurrence",
    "RuleDecl",
    "ScenarioEventDecl",
    "ScenarioEventSet",
    "evaluate_occurrences",
    "load_event_sets",
    "resolve_event_set",
]

"""Decisions and the effects pipeline of a run (architecture 9.4-9.5, M14; Task 4.2).

Pipeline (pure; ``runner.run_mission`` drives it):

1. ``anomalies.evaluate_occurrences`` lists the declared events that occur for the design.
2. Occurrences are processed in event order into a ``RunState``: an occurrence without
   choices applies its effects at once; a decision becomes ``pending`` and is resolved by
   ``apply_decision`` with the player's choice (``decisions[event_id]``) or, when none is
   given, the DEFAULT = the first declared choice (the safest; never terminating), recorded
   with decision_maker ``"ground"`` and rationale ``DEFAULT_RATIONALE`` (the
   DecisionRecord contract has no ``"system"`` maker; the event itself says ``"system"``).
   Applied effects = the occurrence's own effects updated by the choice's effects (the choice
   wins on a shared key). After a termination, later occurrences do not happen.
3. ``flown_plan`` turns the applied effects into the as-flown operations plan (skipped
   observations, missed contacts, reduced contact rates, items cancelled by termination);
   the engine re-analyses that plan, so no formula is duplicated.
4. ``data_loss_bits`` / ``returned_scale`` apply buffer losses: lost bits can no longer be
   downlinked, so downlinked' = min(downlinked, generated - lost) (gameplay approximation).

Termination: a ``terminate`` effect, or a ``soc_delta`` that takes the battery to 0 or
below (``TERMINATION_BATTERY``), ends the mission on that event's day.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Literal

from app.domain.analysis.context import AnalysisContext
from app.domain.errors import DomainValidationError
from app.domain.simulation.anomalies import Occurrence
from app.domain.units.conversions import day_to_s
from app.schemas.mission import MissionState
from app.schemas.simulation import DecisionChoice, DecisionMaker, DecisionRecord

DEFAULT_RATIONALE = "default (no player choice)"
DEFAULT_DECISION_MAKER: DecisionMaker = "ground"
TERMINATION_CHOICE = "terminate"
TERMINATION_BATTERY = "battery-depleted"


@dataclass(frozen=True)
class Decision:
    event_id: str
    mission_day: float
    prompt: str
    choices: tuple[DecisionChoice, ...]
    base_effects: Mapping[str, float] = field(default_factory=dict)

    @property
    def default_choice(self) -> DecisionChoice:
        return self.choices[0]


@dataclass(frozen=True)
class AppliedEffect:
    event_id: str
    mission_day: float
    effects: Mapping[str, float]
    choice_id: str | None = None


@dataclass(frozen=True)
class Termination:
    event_id: str
    mission_day: float
    cause: Literal["terminate", "battery-depleted"]
    choice_id: str | None


@dataclass(frozen=True)
class RunState:
    """Immutable accumulator of what happened so far (updates return a new state)."""

    pending: Mapping[str, Decision] = field(default_factory=dict)
    applied: tuple[AppliedEffect, ...] = ()
    records: tuple[DecisionRecord, ...] = ()
    terminated: Termination | None = None
    # base state of charge before any dip, by mission day (from the analysis energy ledger)
    soc_at: Callable[[float], float] = field(default=lambda _day: 1.0, compare=False)

    def with_pending(self, decision: Decision) -> "RunState":
        return replace(self, pending={**self.pending, decision.event_id: decision})


def _apply(state: RunState, effect: AppliedEffect) -> RunState:
    terminated = state.terminated
    soc_delta = effect.effects.get("soc_delta", 0.0)
    if terminated is None:
        if effect.effects.get("terminate", 0.0) > 0.0:
            terminated = Termination(
                effect.event_id, effect.mission_day, "terminate", effect.choice_id
            )
        elif soc_delta < 0.0 and state.soc_at(effect.mission_day) + soc_delta <= 0.0:
            terminated = Termination(
                effect.event_id, effect.mission_day, "battery-depleted", effect.choice_id
            )
    return replace(state, applied=(*state.applied, effect), terminated=terminated)


def apply_effects(
    state: RunState, event_id: str, mission_day: float, effects: Mapping[str, float]
) -> RunState:
    """Apply an occurrence that offers no choice."""
    return _apply(state, AppliedEffect(event_id, mission_day, dict(effects)))


def apply_decision(
    state: RunState,
    event_id: str,
    choice_id: str,
    *,
    decision_maker: DecisionMaker = "player",
    rationale: str | None = None,
) -> RunState:
    """Resolve the pending decision ``event_id`` with ``choice_id`` (new state returned)."""
    decision = state.pending.get(event_id)
    if decision is None:
        raise DomainValidationError(
            "UNKNOWN_DECISION_EVENT", "decisions", f"no pending decision {event_id!r}"
        )
    choice = next((c for c in decision.choices if c.id == choice_id), None)
    if choice is None:
        raise DomainValidationError(
            "INVALID_CHOICE",
            f"decisions.{event_id}",
            f"{choice_id!r} is not a choice of {event_id} "
            f"(choices: {', '.join(c.id for c in decision.choices)})",
        )
    record = DecisionRecord(
        event_id=event_id,
        choice_id=choice.id,
        decision_maker=decision_maker,
        mission_day=decision.mission_day,
        rationale=rationale if rationale is not None else f"player choice: {choice.label}",
    )
    pending = {k: v for k, v in state.pending.items() if k != event_id}
    state = replace(state, pending=pending, records=(*state.records, record))
    effects = {**decision.base_effects, **choice.effects}
    return _apply(state, AppliedEffect(event_id, decision.mission_day, effects, choice.id))


@dataclass(frozen=True)
class FlownPlan:
    """The as-flown operations plan and what changed against the design's plan."""

    state: MissionState
    observation_index: tuple[int, ...]  # planned index of each flown observation
    contact_index: tuple[int, ...]  # planned index of each flown contact
    skipped_observations: Mapping[int, str]  # planned index -> causing event id
    missed_contacts: Mapping[int, str]
    rate_changed_by: Mapping[int, str]  # planned contact index -> event that cut its rate
    cancelled_observations: int
    cancelled_contacts: int

    @property
    def changed(self) -> bool:
        return bool(
            self.skipped_observations
            or self.missed_contacts
            or self.rate_changed_by
            or self.cancelled_observations
            or self.cancelled_contacts
        )


def _window_hit(applied: Sequence[AppliedEffect], key: str, day: float) -> str | None:
    for a in applied:
        length = a.effects.get(key, 0.0)
        if length > 0.0 and a.mission_day <= day < a.mission_day + length:
            return a.event_id
    return None


def flown_plan(state: MissionState, run: RunState) -> FlownPlan:
    ops = state.operations
    end = run.terminated.mission_day if run.terminated is not None else None
    obs: list[dict[str, object]] = []
    obs_idx: list[int] = []
    skipped: dict[int, str] = {}
    cancelled_obs = 0
    for i, item in enumerate(ops.observation_plan):
        if end is not None and item.start_day >= end:
            cancelled_obs += 1
            continue
        cause = _window_hit(run.applied, "science_time_lost_days", item.start_day)
        if cause is not None:
            skipped[i] = cause
            continue
        obs.append(item.model_dump())
        obs_idx.append(i)
    contacts: list[dict[str, object]] = []
    con_idx: list[int] = []
    missed: dict[int, str] = {}
    rate_by: dict[int, str] = {}
    cancelled_con = 0
    for i, c in enumerate(ops.downlink_plan):
        if end is not None and c.start_day >= end:
            cancelled_con += 1
            continue
        cause = _window_hit(run.applied, "link_outage_days", c.start_day)
        if cause is not None:
            missed[i] = cause
            continue
        rate = c.data_rate_bits_per_second
        for a in run.applied:
            factor = a.effects.get("downlink_rate_factor")
            if factor is not None and a.mission_day <= c.start_day:
                rate *= factor
                rate_by[i] = a.event_id
        contacts.append({**c.model_dump(), "data_rate_bits_per_second": rate})
        con_idx.append(i)
    dump = state.model_dump()
    dump["operations"] = {**dump["operations"], "observation_plan": obs, "downlink_plan": contacts}
    return FlownPlan(
        state=MissionState.model_validate(dump),
        observation_index=tuple(obs_idx),
        contact_index=tuple(con_idx),
        skipped_observations=skipped,
        missed_contacts=missed,
        rate_changed_by=rate_by,
        cancelled_observations=cancelled_obs,
        cancelled_contacts=cancelled_con,
    )


def buffer_bits_at(ctx: AnalysisContext, day: float) -> float:
    """Ledger buffer contents at ``day`` (last step at or before it)."""
    t = day_to_s(day)
    bits = 0.0
    for ts, b in ctx.data.buffer_timeline:
        if ts <= t:
            bits = b
        else:
            break
    return bits


def data_losses(run: RunState, ctx: AnalysisContext) -> tuple[tuple[float, float, str], ...]:
    """(day, lost bits, event id) for every buffer loss, against the flown ledger."""
    out: list[tuple[float, float, str]] = []
    lost = 0.0
    for a in run.applied:
        frac = a.effects.get("buffer_loss_fraction", 0.0)
        if frac <= 0.0:
            continue
        exposed = max(0.0, buffer_bits_at(ctx, a.mission_day) - lost)
        bits = frac * exposed
        lost += bits
        out.append((a.mission_day, bits, a.event_id))
    return tuple(out)


def returned_bits_after_loss(ctx: AnalysisContext, lost_bits: float) -> float:
    return max(0.0, min(ctx.data.downlinked_bits, ctx.data.generated_bits - lost_bits))


def resolve_occurrences(
    occurrences: Sequence[Occurrence],
    chosen: Mapping[str, str],
    *,
    soc_at: Callable[[float], float],
) -> tuple[RunState, tuple[Occurrence, ...]]:
    """Process occurrences in event order; returns the state and the ones that happened."""
    state = RunState(soc_at=soc_at)
    occurred: list[Occurrence] = []
    for occ in occurrences:
        if state.terminated is not None:
            break  # the mission has ended: later events do not happen
        occurred.append(occ)
        decl = occ.decl
        if not decl.choices:
            state = apply_effects(state, occ.event_id, occ.mission_day, decl.effects)
            continue
        decision = Decision(
            event_id=occ.event_id,
            mission_day=occ.mission_day,
            prompt=decl.prompt or "",
            choices=decl.contract_choices(),
            base_effects=dict(decl.effects),
        )
        state = state.with_pending(decision)
        choice_id = chosen.get(occ.event_id)
        if choice_id is None:
            state = apply_decision(
                state,
                occ.event_id,
                decision.default_choice.id,
                decision_maker=DEFAULT_DECISION_MAKER,
                rationale=DEFAULT_RATIONALE,
            )
        else:
            state = apply_decision(state, occ.event_id, choice_id)
    return state, tuple(occurred)


__all__ = [
    "DEFAULT_DECISION_MAKER",
    "DEFAULT_RATIONALE",
    "AppliedEffect",
    "Decision",
    "FlownPlan",
    "RunState",
    "Termination",
    "apply_decision",
    "apply_effects",
    "buffer_bits_at",
    "data_losses",
    "flown_plan",
    "resolve_occurrences",
    "returned_bits_after_loss",
]

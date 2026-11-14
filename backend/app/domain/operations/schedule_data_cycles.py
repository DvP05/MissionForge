"""Greedy science + downlink co-scheduler with data cycles (architecture 19.6).

A deterministic greedy heuristic, not an optimiser: opportunities are considered in order
of (highest expected science, earliest start, id) and each is accepted only if it passes
every check given what is already accepted:

1. POINTING - its attitude is one the spacecraft supports.
2. ENERGY - its energy fits the per-observation energy budget.
3. INSTRUMENT_CONFLICT - it does not overlap an accepted opportunity on the same instrument.
4. Buffer - replaying the whole timeline with it included never exceeds onboard storage.
   If it would, it is rejected as NO_CONTACT when no usable contact follows it, otherwise
   BUFFER_OVERFLOW_BEFORE_CONTACT. With `accept_data_loss` it is kept and the excess
   is recorded as lost data instead.

Buffer rule: buffer_after = buffer_before + generated - downlinked, where a contact
returns min(contact capacity, data already on board) and a contact with negative link
margin returns nothing. Data is counted on board at the end of its observation.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.schemas.operations import (
    BufferPoint,
    ContactWindow,
    MissionSchedule,
    ObservationOpportunity,
    RejectedOpportunity,
    RejectionReason,
    ScheduledDataCycle,
)


@dataclass(frozen=True)
class ScheduleResources:
    buffer_capacity_bits: float
    max_energy_per_observation_joules: float
    supported_attitudes: frozenset[str]
    initial_buffer_bits: float = 0.0


@dataclass(frozen=True)
class SchedulePolicy:
    accept_data_loss: bool = False


@dataclass(frozen=True)
class _Replay:
    timeline: list[BufferPoint]
    overflow_bits: float
    cycles: list[ScheduledDataCycle]


def _usable(c: ContactWindow) -> bool:
    return c.link_margin_db >= 0 and c.max_downlink_bits > 0


def _replay(
    accepted: Sequence[ObservationOpportunity],
    contacts: Sequence[ContactWindow],
    capacity: float,
    initial: float,
) -> _Replay:
    """Walk observations (at their end) and contacts (at their start) in time order."""
    events: list[tuple[float, int, str, ObservationOpportunity | ContactWindow]] = []
    for o in accepted:
        events.append((o.end, 0, o.id, o))
    for c in contacts:
        events.append((c.start, 1, c.id, c))
    events.sort(key=lambda e: (e[0], e[1], e[2]))

    buffer = initial
    lost = 0.0
    timeline = [BufferPoint(t=0.0, bits=buffer)]
    cycles: list[ScheduledDataCycle] = []
    pending: list[str] = []
    for t, _, _, item in events:
        if isinstance(item, ObservationOpportunity):
            buffer += item.generated_data_bits
            if buffer > capacity:
                lost += buffer - capacity
                buffer = capacity
            pending.append(item.id)
        else:
            before = buffer
            sent = min(item.max_downlink_bits, buffer) if _usable(item) else 0.0
            buffer -= sent
            if pending or sent > 0:
                if _usable(item):
                    reason = f"Contact {item.id} returns {sent:.4g} bits"
                else:
                    margin = item.link_margin_db
                    reason = f"Contact {item.id} returns nothing (link margin {margin:.1f} dB)"
                cycles.append(
                    ScheduledDataCycle(
                        id=f"cycle:{item.id}",
                        observations=list(pending),
                        contact_window_id=item.id,
                        buffer_before_bits=before,
                        buffer_after_bits=buffer,
                        explanation=(
                            f"{len(pending)} observation(s) since the last contact. {reason}."
                        ),
                    )
                )
                pending = []
        timeline.append(BufferPoint(t=t, bits=buffer))
    if pending:
        cycles.append(
            ScheduledDataCycle(
                id="cycle:unreturned",
                observations=list(pending),
                contact_window_id=None,
                buffer_before_bits=buffer,
                buffer_after_bits=buffer,
                explanation="No contact after these observations: their data stays on board.",
            )
        )
    return _Replay(timeline, lost, cycles)


def schedule_data_cycles(
    opportunities: Sequence[ObservationOpportunity],
    contacts: Sequence[ContactWindow],
    resources: ScheduleResources,
    policy: SchedulePolicy = SchedulePolicy(),
) -> MissionSchedule:
    capacity = resources.buffer_capacity_bits
    order = sorted(opportunities, key=lambda o: (-o.expected_science_value, o.start, o.id))
    accepted: list[ObservationOpportunity] = []
    rejected: list[RejectedOpportunity] = []

    def reject(o: ObservationOpportunity, reason: RejectionReason) -> None:
        rejected.append(RejectedOpportunity(id=o.id, reason_code=reason))

    for o in order:
        if o.compatible_attitude not in resources.supported_attitudes:
            reject(o, "POINTING")
            continue
        if o.energy_joules > resources.max_energy_per_observation_joules:
            reject(o, "ENERGY")
            continue
        if any(
            a.instrument_id == o.instrument_id and a.start < o.end and o.start < a.end
            for a in accepted
        ):
            reject(o, "INSTRUMENT_CONFLICT")
            continue
        trial = _replay([*accepted, o], contacts, capacity, resources.initial_buffer_bits)
        if trial.overflow_bits > 0 and not policy.accept_data_loss:
            later = any(_usable(c) and c.start >= o.end for c in contacts)
            reject(o, "BUFFER_OVERFLOW_BEFORE_CONTACT" if later else "NO_CONTACT")
            continue
        accepted.append(o)

    accepted.sort(key=lambda o: (o.start, o.id))
    final = _replay(accepted, contacts, capacity, resources.initial_buffer_bits)
    return MissionSchedule(
        accepted=[o.id for o in accepted],
        rejected=rejected,
        cycles=final.cycles,
        buffer_timeline=final.timeline,
        data_loss_risk_accepted=policy.accept_data_loss,
        data_lost_bits=final.overflow_bits,
    )

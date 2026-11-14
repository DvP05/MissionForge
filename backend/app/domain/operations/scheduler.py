"""Deterministic greedy science and downlink scheduler."""

from collections.abc import Sequence

from app.schemas.operations import (
    BufferPoint,
    ContactWindow,
    MissionSchedule,
    ObservationOpportunity,
    RejectedOpportunity,
    ScheduledDataCycle,
)


def _simulate(
    observations: Sequence[ObservationOpportunity],
    contacts: Sequence[ContactWindow],
    capacity_bits: float,
) -> tuple[bool, list[BufferPoint], float]:
    events: list[tuple[float, int, str, float]] = []
    for observation in observations:
        events.append((observation.start, 1, observation.id, observation.generated_data_bits))
    for contact in contacts:
        events.append((contact.start, 0, contact.id, contact.max_downlink_bits))
    buffer = 0.0
    timeline: list[BufferPoint] = [BufferPoint(t=0.0, bits=0.0)]
    for timestamp, kind, _event_id, amount in sorted(
        events, key=lambda item: (item[0], item[1], item[2])
    ):
        if kind == 0:
            drained = min(buffer, amount)
            buffer -= drained
        else:
            buffer += amount
        timeline.append(BufferPoint(t=timestamp, bits=buffer))
        if buffer > capacity_bits:
            return False, timeline, buffer
    return True, timeline, buffer


def _contact_for(
    observation: ObservationOpportunity,
    contacts: Sequence[ContactWindow],
) -> ContactWindow | None:
    return next((contact for contact in contacts if contact.start >= observation.end), None)


def schedule_data_cycle(
    opportunities: Sequence[ObservationOpportunity],
    contacts: Sequence[ContactWindow],
    *,
    storage_capacity_bits: float,
    initial_buffer_bits: float = 0.0,
    available_energy_joules: float | None = None,
) -> MissionSchedule:
    """Schedule observations by value, then validate them chronologically."""
    if storage_capacity_bits < 0 or initial_buffer_bits < 0:
        raise ValueError("storage capacity and initial buffer must be non-negative")
    if initial_buffer_bits > storage_capacity_bits:
        raise ValueError("initial buffer cannot exceed storage capacity")

    ordered = sorted(
        opportunities,
        key=lambda item: (-item.expected_science_value, item.start, item.id),
    )
    accepted: list[ObservationOpportunity] = []
    rejected: list[RejectedOpportunity] = []
    energy_used = 0.0
    for candidate in ordered:
        if any(
            candidate.instrument_id == other.instrument_id
            and candidate.start < other.end
            and other.start < candidate.end
            for other in accepted
        ):
            rejected.append(RejectedOpportunity(id=candidate.id, reason_code="INSTRUMENT_CONFLICT"))
            continue
        if (
            available_energy_joules is not None
            and energy_used + candidate.energy_joules > available_energy_joules
        ):
            rejected.append(RejectedOpportunity(id=candidate.id, reason_code="ENERGY"))
            continue
        contact = _contact_for(candidate, contacts)
        if contact is None:
            rejected.append(RejectedOpportunity(id=candidate.id, reason_code="NO_CONTACT"))
            continue
        feasible, _, _ = _simulate(
            accepted + [candidate],
            contacts,
            storage_capacity_bits - initial_buffer_bits,
        )
        if not feasible:
            rejected.append(
                RejectedOpportunity(id=candidate.id, reason_code="BUFFER_OVERFLOW_BEFORE_CONTACT")
            )
            continue
        accepted.append(candidate)
        energy_used += candidate.energy_joules

    accepted.sort(key=lambda item: (item.start, item.id))
    contacts_sorted = sorted(contacts, key=lambda item: (item.start, item.id))
    remaining_capacity = {contact.id: contact.max_downlink_bits for contact in contacts_sorted}
    cycles: list[ScheduledDataCycle] = []
    buffer = initial_buffer_bits
    for observation in accepted:
        before = buffer
        buffer += observation.generated_data_bits
        contact = next(
            (
                candidate
                for candidate in contacts_sorted
                if candidate.start >= observation.end and remaining_capacity[candidate.id] > 0
            ),
            None,
        )
        if contact is not None:
            drained = min(buffer, remaining_capacity[contact.id])
            buffer -= drained
            remaining_capacity[contact.id] -= drained
        cycles.append(
            ScheduledDataCycle(
                id=f"cycle:{observation.id}",
                observations=[observation.id],
                contact_window_id=contact.id if contact else None,
                buffer_before_bits=before,
                buffer_after_bits=buffer,
                explanation=(
                    f"Accepted for {observation.expected_science_value:g} expected science value; "
                    f"downlink uses {contact.id}."
                    if contact
                    else "Accepted without a following contact."
                ),
            )
        )
    feasible, timeline, _ = _simulate(
        accepted,
        contacts_sorted,
        storage_capacity_bits - initial_buffer_bits,
    )
    if not feasible:
        raise RuntimeError("scheduler produced a buffer overflow")
    if initial_buffer_bits:
        timeline = [
            BufferPoint(t=point.t, bits=point.bits + initial_buffer_bits) for point in timeline
        ]
    return MissionSchedule(
        accepted=[observation.id for observation in accepted],
        rejected=rejected,
        cycles=cycles,
        buffer_timeline=timeline,
    )

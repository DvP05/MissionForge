"""Greedy science/downlink scheduler (Task 6.6, architecture 19.6 / 21)."""

import time

from app.domain.operations import (
    SchedulePolicy,
    ScheduleResources,
    build_schedule_inputs,
    schedule_data_cycles,
)
from app.schemas.operations import ContactWindow, ObservationOpportunity

from ..architecture_graph._support import analyse, catalog, edit_arch, state

RES = ScheduleResources(
    buffer_capacity_bits=100.0,
    max_energy_per_observation_joules=50.0,
    supported_attitudes=frozenset({"target-pointing"}),
)


def opp(
    oid: str,
    start: float,
    end: float,
    bits: float,
    value: float = 1.0,
    inst: str = "cam",
    energy: float = 10.0,
    attitude: str = "target-pointing",
) -> ObservationOpportunity:  # noqa: PLR0913
    return ObservationOpportunity(
        id=oid, start=start, end=end, instrument_id=inst, expected_science_value=value,
        generated_data_bits=bits, energy_joules=energy, slew_seconds=0.0,
        compatible_attitude=attitude,
    )  # fmt: skip


def contact(cid: str, start: float, bits: float, margin: float = 3.0) -> ContactWindow:
    return ContactWindow(
        id=cid,
        start=start,
        end=start + 10,
        max_downlink_bits=bits,
        station_id="gs",
        link_margin_db=margin,
    )


def _check_invariants(schedule, contacts, capacity: float) -> None:  # type: ignore[no-untyped-def]
    assert all(p.bits <= capacity + 1e-9 for p in schedule.buffer_timeline)
    by_id = {c.id: c for c in contacts}
    for cyc in schedule.cycles:
        sent = cyc.buffer_before_bits - cyc.buffer_after_bits
        assert sent >= -1e-9
        if cyc.contact_window_id is not None:
            assert sent <= by_id[cyc.contact_window_id].max_downlink_bits + 1e-9
            assert sent <= cyc.buffer_before_bits + 1e-9


def test_buffer_never_exceeds_capacity_and_overflow_rejected() -> None:
    opps = [
        opp("a", 0, 10, 60, value=3),
        opp("b", 20, 30, 60, value=2),
        opp("c", 50, 60, 60, value=1),
    ]
    contacts = [contact("k1", 40, 100)]
    s = schedule_data_cycles(opps, contacts, RES)
    assert s.accepted == ["a", "c"]
    assert [(r.id, r.reason_code) for r in s.rejected] == [("b", "BUFFER_OVERFLOW_BEFORE_CONTACT")]
    assert s.data_lost_bits == 0
    _check_invariants(s, contacts, RES.buffer_capacity_bits)


def test_downlink_bounded_by_capacity_and_buffer() -> None:
    opps = [opp("a", 0, 10, 80)]
    contacts = [contact("k1", 20, 30), contact("k2", 40, 500)]
    s = schedule_data_cycles(opps, contacts, RES)
    assert [c.buffer_before_bits - c.buffer_after_bits for c in s.cycles] == [30, 50]
    _check_invariants(s, contacts, RES.buffer_capacity_bits)


def test_cannot_downlink_data_not_yet_generated() -> None:
    s = schedule_data_cycles([opp("a", 50, 60, 40)], [contact("k1", 10, 1000)], RES)
    assert s.buffer_timeline[-1].bits == 40  # the early contact had nothing to send


def test_negative_link_margin_returns_nothing() -> None:
    s = schedule_data_cycles([opp("a", 0, 10, 40)], [contact("k1", 20, 1000, margin=-2)], RES)
    assert s.cycles[0].buffer_after_bits == 40


def test_instrument_conflict_pointing_and_energy() -> None:
    opps = [
        opp("a", 0, 10, 1, value=5),
        opp("b", 5, 15, 1, value=4),  # overlaps a on the same instrument
        opp("c", 5, 15, 1, value=3, inst="spec"),  # different instrument: fine
        opp("d", 30, 40, 1, value=2, attitude="precision-pointing"),
        opp("e", 50, 60, 1, value=1, energy=500),
    ]
    s = schedule_data_cycles(opps, [contact("k", 100, 100)], RES)
    assert s.accepted == ["a", "c"]
    assert {r.id: r.reason_code for r in s.rejected} == {
        "b": "INSTRUMENT_CONFLICT", "d": "POINTING", "e": "ENERGY",
    }  # fmt: skip


def test_empty_contacts_accept_what_fits_reject_rest() -> None:
    opps = [opp("a", 0, 10, 60, value=2), opp("b", 20, 30, 60, value=1)]
    s = schedule_data_cycles(opps, [], RES)
    assert s.accepted == ["a"]
    assert [(r.id, r.reason_code) for r in s.rejected] == [("b", "NO_CONTACT")]
    assert s.cycles[-1].contact_window_id is None


def test_accepting_data_loss_is_explicit() -> None:
    opps = [opp("a", 0, 10, 80), opp("b", 20, 30, 80)]
    s = schedule_data_cycles(opps, [], RES, SchedulePolicy(accept_data_loss=True))
    assert s.accepted == ["a", "b"] and s.data_loss_risk_accepted
    assert s.data_lost_bits == 60
    _check_invariants(s, [], RES.buffer_capacity_bits)


def test_zero_inputs() -> None:
    s = schedule_data_cycles([], [], RES)
    assert s.accepted == [] and s.rejected == [] and s.cycles == []


def test_deterministic() -> None:
    opps = [opp(f"o{i}", i * 7, i * 7 + 5, 20 + i % 3, value=i % 4) for i in range(20)]
    contacts = [contact(f"k{i}", i * 30, 50) for i in range(5)]
    assert schedule_data_cycles(opps, contacts, RES) == schedule_data_cycles(opps, contacts, RES)


def test_fifty_by_ten_under_100ms() -> None:
    opps = [
        opp(f"o{i:02}", i * 100, i * 100 + 50, 30, value=(i * 7) % 11, inst=f"i{i % 3}")
        for i in range(50)
    ]
    contacts = [contact(f"k{i}", i * 500 + 60, 200) for i in range(10)]
    big = ScheduleResources(1000.0, 50.0, frozenset({"target-pointing"}))
    start = time.perf_counter()
    schedule_data_cycles(opps, contacts, big)
    assert time.perf_counter() - start < 0.1


def test_inputs_from_design_trace_to_requirements() -> None:
    s = state()
    inputs = build_schedule_inputs(s, analyse(s), catalog())
    measurements = {r.id for o in s.science_objectives for r in o.required_measurements}
    sched = schedule_data_cycles(inputs.opportunities, inputs.contacts, inputs.resources)
    assert sched.accepted
    assert all(inputs.measurement_of[a] in measurements for a in sched.accepted)
    # Starter radio cannot close the link, so contacts return nothing.
    assert all(c.link_margin_db < 0 for c in inputs.contacts)
    fixed = edit_arch(s, communications_id="comms-xband-medium")
    fixed_inputs = build_schedule_inputs(fixed, analyse(fixed), catalog())
    assert all(c.link_margin_db >= 0 for c in fixed_inputs.contacts)


def test_small_storage_rejects_observations() -> None:
    s = edit_arch(state(), cdh_id="cdh-basic", communications_id="comms-xband-medium")
    inputs = build_schedule_inputs(s, analyse(s), catalog())
    sched = schedule_data_cycles(inputs.opportunities, inputs.contacts, inputs.resources)
    assert {r.reason_code for r in sched.rejected} == {"BUFFER_OVERFLOW_BEFORE_CONTACT"}

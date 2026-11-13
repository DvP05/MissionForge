from datetime import UTC, datetime
from typing import Any

import pytest

from app.config import DEFAULT_CATALOG_DIR, DEFAULT_MISSIONS_DIR
from app.domain.analysis.comms import link_budget, link_input_from_components
from app.domain.analysis.data import (
    PROTOCOL_EFFICIENCY,
    ContactEvent,
    ObservationEvent,
    contact_events_from_plan,
    contact_rate_bps,
    data_ledger,
    observation_events_from_plan,
)
from app.domain.catalog.loader import load_catalog
from app.domain.errors import DomainValidationError
from app.domain.mission.defaults import default_mission_state, list_templates


def obs(t: float, dur: float = 100.0, rate: float = 10.0, duty: float = 1.0) -> ObservationEvent:
    return ObservationEvent(t, dur, rate, duty)


def con(
    t: float,
    dur: float = 100.0,
    planned: float = 10.0,
    mx: float = 100.0,
    margin: float = 5.0,
    avail: float = 1.0,
) -> ContactEvent:
    return ContactEvent(t, dur, planned, mx, margin, avail)


def test_protocol_efficiency_constant() -> None:
    assert PROTOCOL_EFFICIENCY == 0.9


def test_zero_contacts_means_nothing_downlinked_and_no_div_by_zero() -> None:
    led = data_ledger([obs(0.0)], [], 1.0e6)
    assert led.generated_bits == 1000.0
    assert led.downlinked_bits == 0.0
    assert led.end_buffer_bits == 1000.0
    assert led.margin_fraction == -1.0


def test_zero_generated_has_zero_margin_convention() -> None:
    led = data_ledger([], [con(0.0)], 1.0e6)
    assert led.generated_bits == 0.0 and led.margin_fraction == 0.0
    assert led.downlinked_bits == 0.0


def test_cannot_downlink_data_not_yet_generated() -> None:
    led = data_ledger([obs(500.0)], [con(0.0, planned=100.0)], 1.0e6)
    assert led.downlinked_bits == 0.0
    assert led.per_contact[0].capacity_bits == pytest.approx(100 * 100 * 0.9)
    assert led.per_contact[0].downlinked_bits == 0.0


def test_downlink_limited_by_capacity_then_buffer() -> None:
    led = data_ledger([obs(0.0)], [con(10.0, planned=5.0)], 1.0e6)
    assert led.downlinked_bits == pytest.approx(5.0 * 100.0 * 0.9)
    assert led.end_buffer_bits == pytest.approx(1000.0 - 450.0)
    led2 = data_ledger([obs(0.0)], [con(10.0, planned=100.0)], 1.0e6)
    assert led2.downlinked_bits == 1000.0 and led2.end_buffer_bits == 0.0
    assert led2.margin_fraction == 0.0


def test_negative_margin_contact_contributes_nothing() -> None:
    led = data_ledger([obs(0.0)], [con(10.0, margin=-0.01)], 1.0e6)
    assert led.downlinked_bits == 0.0 and led.per_contact[0].rate_bps == 0.0


def test_rate_capped_by_hardware_and_availability_applied() -> None:
    assert contact_rate_bps(50.0, 20.0, 1.0) == 20.0
    assert contact_rate_bps(10.0, 20.0, 0.0) == 10.0
    assert contact_rate_bps(10.0, 20.0, -1e-9) == 0.0
    led = data_ledger([obs(0.0, rate=1000.0)], [con(1.0, planned=50.0, mx=20.0, avail=0.5)], 1e9)
    assert led.downlinked_bits == pytest.approx(20.0 * 100.0 * 0.9 * 0.5)


def test_buffer_clamps_and_overflow_flagged() -> None:
    led = data_ledger([obs(0.0), obs(200.0)], [], 1500.0)
    assert led.generated_bits == 2000.0
    assert led.peak_buffer_bits == 1500.0 and led.overflow_bits == 500.0
    assert all(b <= 1500.0 for _, b in led.buffer_timeline)
    assert led.end_buffer_bits + led.overflow_bits + led.downlinked_bits == led.generated_bits


def test_no_overflow_when_downlink_frees_room_in_time() -> None:
    led = data_ledger([obs(0.0), obs(200.0)], [con(100.0, planned=100.0)], 1100.0)
    assert led.overflow_bits == 0.0 and led.peak_buffer_bits <= 1100.0


def test_events_are_processed_chronologically_regardless_of_input_order() -> None:
    a = data_ledger([obs(200.0), obs(0.0)], [con(150.0, planned=100.0)], 1e6)
    b = data_ledger([obs(0.0), obs(200.0)], [con(150.0, planned=100.0)], 1e6)
    assert a == b
    assert [t for t, _ in a.buffer_timeline] == [0.0, 150.0, 200.0]


def test_compression_and_duty_cycle_scale_generation() -> None:
    led = data_ledger([obs(0.0, duty=0.5)], [], 1e6, compression=0.5)
    assert led.generated_bits == pytest.approx(250.0)


def test_buffer_end_formula_single_pair() -> None:
    led = data_ledger([obs(0.0)], [con(1.0, planned=2.0)], 1e6)
    assert led.buffer_timeline[-1][1] == pytest.approx(max(0.0, 1000.0 - 2.0 * 100.0 * 0.9))


@pytest.mark.parametrize(
    "kwargs",
    [{"buffer_capacity_bits": 0.0}, {"protocol_eff": 1.5}, {"compression": 0.0}],
)
def test_invalid_ledger_parameters(kwargs: dict[str, float]) -> None:
    args: dict[str, Any] = {"buffer_capacity_bits": 1e6, **kwargs}
    with pytest.raises(DomainValidationError):
        data_ledger([], [], **args)


def test_negative_inputs_rejected() -> None:
    with pytest.raises(DomainValidationError):
        data_ledger([obs(-1.0)], [], 1e6)
    with pytest.raises(DomainValidationError):
        data_ledger([obs(0.0, dur=-1.0)], [], 1e6)
    with pytest.raises(DomainValidationError):
        data_ledger([], [con(0.0, avail=1.5)], 1e6)


# --- bridge to the template tests: NEO starter, real catalogue ----------------------------

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
CATALOG = load_catalog(DEFAULT_CATALOG_DIR)


def _neo(comms_id: str) -> tuple[Any, Any, Any, list[ObservationEvent], list[ContactEvent], float]:
    tpl = {t.scenario_id: t for t in list_templates(DEFAULT_MISSIONS_DIR)}["neo-rendezvous"]
    state = default_mission_state(
        "neo-rendezvous", mission_id="m-1", seed=42, now=NOW, templates_dir=DEFAULT_MISSIONS_DIR
    )
    cap_rate: dict[str, float] = {}
    for iid in state.architecture.instrument_ids:
        comp = CATALOG.get(iid)
        for cap in comp.capabilities:
            cap_rate[cap] = max(cap_rate.get(cap, 0.0), comp.parameters["data_rate"].value)
    rates = {
        m.id: cap_rate[m.instrument_capability]
        for o in state.science_objectives
        for m in o.required_measurements
    }
    observations = observation_events_from_plan(state.operations.observation_plan, rates)
    ground = CATALOG.get(state.architecture.ground_segment_id)
    contacts = contact_events_from_plan(
        state.operations.downlink_plan,
        CATALOG.get(comms_id),
        ground,
        range_m=tpl.reference_earth_range_m,
    )
    storage = CATALOG.get(state.architecture.cdh_id).parameters["storage"].value
    return state, tpl, ground, observations, contacts, storage


def test_neo_link_margins_reproduce_template_numbers() -> None:
    state, tpl, ground, *_ = _neo("comms-xband-lowgain")
    planned = state.operations.downlink_plan[0].data_rate_bits_per_second
    assert planned == 50_000.0
    for cid, expected in (("comms-xband-medium", 6.71), ("comms-xband-lowgain", -22.31)):
        li = link_input_from_components(
            CATALOG.get(cid), ground, range_m=tpl.reference_earth_range_m, bit_rate_bps=planned
        )
        assert link_budget(li).margin_db == pytest.approx(expected, abs=0.01)


def test_neo_data_return_shortfall_and_fix_via_domain_ledger() -> None:
    _, _, _, obs_lo, con_lo, storage = _neo("comms-xband-lowgain")
    low = data_ledger(obs_lo, con_lo, storage)
    state, _, _, obs_md, con_md, storage_md = _neo("comms-xband-medium")
    med = data_ledger(obs_md, con_md, storage_md)
    assert low.generated_bits == pytest.approx(12.96e9, rel=1e-3)
    assert low.downlinked_bits == 0.0 and low.margin_fraction == -1.0  # shortfall
    assert med.downlinked_bits == pytest.approx(med.generated_bits)  # backlog cleared
    assert med.overflow_bits == 0.0 and low.overflow_bits == 0.0
    # medium's contact capacity is the template-pinned ~17.107 Gbit (>= 1.2x generated)
    capacity = sum(c.capacity_bits for c in med.per_contact)
    assert capacity == pytest.approx(17.107e9, rel=1e-3)
    assert capacity >= med.generated_bits * (1.0 + state.constraints.data_margin_fraction)


def test_unknown_measurement_in_plan_rejected() -> None:
    state, *_ = _neo("comms-xband-medium")
    with pytest.raises(DomainValidationError) as e:
        observation_events_from_plan(state.operations.observation_plan, {})
    assert e.value.code == "UNKNOWN_MEASUREMENT"

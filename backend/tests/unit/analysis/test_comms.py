import math

import pytest

from app.domain.analysis.comms import (
    LinkInput,
    fspl_db,
    link_budget,
    link_input_from_components,
)
from app.domain.errors import DomainValidationError
from app.schemas.catalog import CatalogComponent

PROV = {"fidelity": "gameplay-estimate", "source_name": "t", "assumptions": ["t"]}


def q(v: float, u: str) -> dict[str, object]:
    return {"value": v, "unit": u, "provenance": PROV}


def comp(cid: str, params: dict[str, dict[str, object]]) -> CatalogComponent:
    return CatalogComponent.model_validate(
        {
            "id": cid, "name": cid, "category": "communications", "description": "d", "tags": [],
            "parameters": params, "source_record_id": "s", "provenance": PROV,
            "is_illustrative": True,
        }
    )  # fmt: skip


BASE = LinkInput(
    tx_power_w=5.0,
    tx_gain_dbi=10.0,
    rx_gain_dbi=60.0,
    frequency_hz=8.4e9,
    range_m=3.74e10,
    system_noise_temp_k=50.0,
    bit_rate_bps=5.0e4,
    required_ebn0_db=2.5,
    implementation_loss_db=2.0,
)


def test_fspl_tenfold_range_adds_20_db() -> None:
    assert fspl_db(1.0e9, 8.4e9) - fspl_db(1.0e8, 8.4e9) == pytest.approx(20.0, abs=1e-9)


def test_fspl_double_frequency_adds_6_0206_db() -> None:
    assert fspl_db(1.0e9, 1.6e10) - fspl_db(1.0e9, 8.0e9) == pytest.approx(6.0206, abs=1e-4)


def test_fspl_known_value() -> None:
    lam = 299792458.0 / 8.4e9
    assert fspl_db(3.0e10, 8.4e9) == pytest.approx(20 * math.log10(4 * math.pi * 3.0e10 / lam))


def test_link_chain_and_margin_is_ebn0_minus_required() -> None:
    r = link_budget(BASE)
    assert r.eirp_dbw == pytest.approx(10 * math.log10(5.0) + 10.0)
    assert r.pr_dbw == pytest.approx(r.eirp_dbw + 60.0 - r.fspl_db - 2.0)
    assert r.n0_dbw_per_hz == pytest.approx(10 * math.log10(1.380649e-23 * 50.0))
    assert r.cn0_dbhz == pytest.approx(r.pr_dbw - r.n0_dbw_per_hz)
    assert r.ebn0_db == pytest.approx(r.cn0_dbhz - 10 * math.log10(5.0e4))
    assert r.margin_db == pytest.approx(r.ebn0_db - 2.5)


def test_other_losses_reduce_margin_one_for_one() -> None:
    a = link_budget(BASE)
    b = link_budget(LinkInput(**{**BASE.__dict__, "other_losses_db": 3.0}))
    assert a.margin_db - b.margin_db == pytest.approx(3.0)


def test_capacity_is_rate_where_margin_is_zero() -> None:
    r = link_budget(BASE)
    at_cap = link_budget(LinkInput(**{**BASE.__dict__, "bit_rate_bps": r.capacity_bps}))
    assert at_cap.margin_db == pytest.approx(0.0, abs=1e-9)
    assert (r.capacity_bps > BASE.bit_rate_bps) == (r.margin_db > 0)


def test_doubling_rate_costs_3_db() -> None:
    a = link_budget(BASE)
    b = link_budget(LinkInput(**{**BASE.__dict__, "bit_rate_bps": 1.0e5}))
    assert a.margin_db - b.margin_db == pytest.approx(10 * math.log10(2.0))


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("tx_power_w", 0.0, "NOT_POSITIVE"),
        ("tx_power_w", float("nan"), "NOT_FINITE"),
        ("range_m", -1.0, "NOT_POSITIVE"),
        ("bit_rate_bps", 0.0, "NOT_POSITIVE"),
        ("system_noise_temp_k", 0.0, "NOT_POSITIVE"),
        ("frequency_hz", 0.0, "NOT_POSITIVE"),
        ("implementation_loss_db", -1.0, "NEGATIVE_LOSS"),
        ("other_losses_db", -1.0, "NEGATIVE_LOSS"),
    ],
)
def test_invalid_inputs_rejected(field: str, value: float, code: str) -> None:
    with pytest.raises(DomainValidationError) as e:
        link_budget(LinkInput(**{**BASE.__dict__, field: value}))
    assert e.value.code == code


RADIO = {
    "antenna_gain": q(10.0, "dB"),
    "frequency": q(8.4e9, "Hz"),
    "required_ebn0": q(2.5, "dB"),
    "implementation_loss": q(2.0, "dB"),
}
GROUND = comp("g1", {"station_gain": q(60.0, "dB"), "noise_temperature": q(50.0, "K")})


def test_dbw_passed_as_watts_unit_is_caught() -> None:
    radio = comp("c1", {**RADIO, "tx_power": q(7.0, "dBW")})
    with pytest.raises(DomainValidationError) as e:
        link_input_from_components(radio, GROUND, range_m=1e9, bit_rate_bps=1e4)
    assert e.value.code == "WRONG_UNIT"


def test_from_components_reads_catalogue_keys() -> None:
    radio = comp("c1", {**RADIO, "tx_power": q(5.0, "W")})
    li = link_input_from_components(radio, GROUND, range_m=3.74e10, bit_rate_bps=5.0e4)
    assert li == BASE
    with pytest.raises(DomainValidationError) as e:
        link_input_from_components(comp("c2", {}), GROUND, range_m=1e9, bit_rate_bps=1e4)
    assert e.value.code == "MISSING_PARAMETER"

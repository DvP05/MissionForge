import math

import pytest

from app.domain.analysis.power import (
    Battery,
    Load,
    PowerPhase,
    array_generation_w,
    average_power_w,
    battery_from_component,
    eclipse_battery_required_wh,
    energy_ledger,
    peak_power_w,
    power_check,
    solar_array_params,
    solar_flux_at,
    solar_generation_w,
)
from app.domain.errors import DomainValidationError
from app.domain.units.constants import SOLAR_CONSTANT_W_M2
from app.schemas.catalog import CatalogComponent

PROV = {"fidelity": "gameplay-estimate", "source_name": "t", "assumptions": ["t"]}
LOADS = [Load("a", 10.0, 0.5), Load("b", 20.0, 1.0)]


def power_comp(unit_cap: str = "Wh", drop: str | None = None) -> CatalogComponent:
    def q(v: float, u: str) -> dict[str, object]:
        return {"value": v, "unit": u, "provenance": PROV}

    params = {
        "mass": q(5.0, "kg"),
        "array_power_at_1au": q(100.0, "W"),
        "battery_capacity": q(50.0, unit_cap),
        "usable_dod": q(0.8, "fraction"),
        "eps_efficiency": q(0.9, "fraction"),
    }
    if drop:
        del params[drop]
    return CatalogComponent.model_validate(
        {
            "id": "pw", "name": "pw", "category": "power", "description": "d", "tags": [],
            "parameters": params, "source_record_id": "s", "provenance": PROV,
            "is_illustrative": True,
        }
    )  # fmt: skip


def test_average_and_peak_reported_separately() -> None:
    assert average_power_w(LOADS) == pytest.approx(25.0)
    assert peak_power_w(LOADS) == pytest.approx(30.0)


def test_peak_ignores_zero_duty_loads() -> None:
    assert peak_power_w([*LOADS, Load("off", 100.0, 0.0)]) == pytest.approx(30.0)


def test_empty_loads_zero() -> None:
    assert average_power_w([]) == 0.0
    assert peak_power_w([]) == 0.0


def test_invalid_loads() -> None:
    with pytest.raises(DomainValidationError):
        average_power_w([Load("x", -1.0, 0.5)])
    with pytest.raises(DomainValidationError):
        average_power_w([Load("x", 1.0, 1.5)])
    with pytest.raises(DomainValidationError):
        peak_power_w([Load("x", math.nan, 0.5)])


def test_flux_inverse_square() -> None:
    assert solar_flux_at(1.0) == pytest.approx(SOLAR_CONSTANT_W_M2)
    assert solar_flux_at(2.0) == pytest.approx(SOLAR_CONSTANT_W_M2 / 4.0)
    with pytest.raises(DomainValidationError):
        solar_flux_at(0.0)


def test_solar_generation_general_formula() -> None:
    assert solar_generation_w(1000.0, 2.0, 0.3, 0.9, 0.0) == pytest.approx(540.0)


def test_incidence_60deg_halves() -> None:
    full = solar_generation_w(1000.0, 2.0, 0.3, 0.9, 0.0)
    assert solar_generation_w(1000.0, 2.0, 0.3, 0.9, math.radians(60)) == pytest.approx(full / 2)
    assert array_generation_w(100.0, 1.0, 0.9, math.radians(60)) == pytest.approx(45.0)


def test_incidence_beyond_90_is_zero_not_negative() -> None:
    assert solar_generation_w(1000.0, 2.0, 0.3, 0.9, math.radians(120)) == 0.0
    assert array_generation_w(100.0, 1.0, 0.9, math.radians(170)) == 0.0


def test_array_generation_scales_inverse_square() -> None:
    assert array_generation_w(100.0, 2.0, 0.9, 0.0) == pytest.approx(22.5)
    with pytest.raises(DomainValidationError):
        array_generation_w(100.0, 0.0, 0.9, 0.0)
    with pytest.raises(DomainValidationError):
        array_generation_w(100.0, 1.0, 1.5, 0.0)


def test_eclipse_battery_required() -> None:
    assert eclipse_battery_required_wh(40.0, 35 * 60.0, 0.8, 0.9) == pytest.approx(32.4, abs=0.1)
    with pytest.raises(DomainValidationError):
        eclipse_battery_required_wh(40.0, 2100.0, 0.0, 0.9)


def test_ledger_clamps_at_capacity() -> None:
    bat = Battery(capacity_wh=10.0, usable_dod=0.8, discharge_efficiency=1.0)
    led = energy_ledger([PowerPhase("sun", 3600.0, 100.0, (Load("l", 10.0, 1.0),))], bat)
    p = led.per_phase[0]
    assert p.end_wh == pytest.approx(10.0)
    assert p.generation_wh == pytest.approx(100.0)
    assert p.consumption_wh == pytest.approx(10.0)
    assert led.closes and led.min_soc_fraction == pytest.approx(1.0)


def test_ledger_clamps_at_zero_and_fails() -> None:
    bat = Battery(10.0, 0.8, 1.0)
    led = energy_ledger([PowerPhase("ecl", 7200.0, 0.0, (Load("l", 50.0, 1.0),))], bat)
    p = led.per_phase[0]
    assert p.end_wh == 0.0
    assert p.unmet_wh == pytest.approx(90.0)
    assert led.min_soc_fraction == 0.0
    assert not led.closes


def test_ledger_soc_floor_enforced() -> None:
    bat = Battery(100.0, 0.5, 1.0)  # floor 50 %
    ok = energy_ledger([PowerPhase("e", 3600.0, 0.0, (Load("l", 40.0, 1.0),))], bat)
    assert ok.closes and ok.min_soc_fraction == pytest.approx(0.6)
    bad = energy_ledger([PowerPhase("e", 3600.0, 0.0, (Load("l", 60.0, 1.0),))], bat)
    assert not bad.closes and bad.min_soc_fraction == pytest.approx(0.4)


def test_ledger_discharge_efficiency_and_recharge() -> None:
    bat = Battery(100.0, 0.8, 0.9)
    led = energy_ledger(
        [
            PowerPhase("ecl", 3600.0, 0.0, (Load("l", 18.0, 1.0),)),  # draws 20 Wh from battery
            PowerPhase("sun", 3600.0, 15.0, (Load("l", 5.0, 1.0),)),  # +10 Wh
        ],
        bat,
    )
    assert led.per_phase[0].end_wh == pytest.approx(80.0)
    assert led.per_phase[1].end_wh == pytest.approx(90.0)
    assert led.min_soc_fraction == pytest.approx(0.8)
    assert led.closes


def test_ledger_empty_and_validation() -> None:
    bat = Battery(10.0, 0.8, 0.9)
    led = energy_ledger([], bat)
    assert led.closes and led.min_soc_fraction == 1.0 and led.per_phase == ()
    with pytest.raises(DomainValidationError):
        energy_ledger([], Battery(0.0, 0.8, 0.9))
    with pytest.raises(DomainValidationError):
        energy_ledger([PowerPhase("x", -1.0, 0.0, ())], bat)
    with pytest.raises(DomainValidationError):
        energy_ledger([PowerPhase("x", 1.0, -1.0, ())], bat)
    with pytest.raises(DomainValidationError):
        energy_ledger([], Battery(10.0, 0.8, 0.0))


def test_ledger_labels() -> None:
    led = energy_ledger([], Battery(10.0, 0.8, 0.9))
    assert led.model_id == "power-v1"
    assert led.provenance.fidelity == "derived"
    assert any("simultaneous" in a for a in led.assumptions)


def test_passes_average_fails_peak() -> None:
    avg, peak = average_power_w(LOADS), peak_power_w(LOADS)  # 25 / 30
    chk = power_check(avg, peak, supply_w=27.0, margin_fraction=0.0)
    assert chk.avg_ok and not chk.peak_ok
    assert (chk.peak_ok, chk.avg_ok) == (False, True)
    assert chk.avg_margin_w == pytest.approx(2.0)
    assert chk.peak_margin_w == pytest.approx(-3.0)


def test_power_check_margin_and_validation() -> None:
    assert not power_check(25.0, 25.0, 27.0, 0.2).avg_ok  # 25*1.2 = 30 > 27
    assert power_check(25.0, 30.0, 40.0, 0.2).peak_ok
    with pytest.raises(DomainValidationError):
        power_check(25.0, 30.0, 40.0, -0.1)


def test_component_params_units_enforced() -> None:
    arr = solar_array_params(power_comp())
    assert arr.array_power_at_1au_w == 100.0 and arr.eps_efficiency == 0.9
    bat = battery_from_component(power_comp(), discharge_efficiency=0.9)
    assert bat == Battery(50.0, 0.8, 0.9)
    with pytest.raises(DomainValidationError) as e:  # Wh vs W never mixed
        battery_from_component(power_comp(unit_cap="W"), discharge_efficiency=0.9)
    assert e.value.code == "WRONG_UNIT"
    with pytest.raises(DomainValidationError) as e2:
        solar_array_params(power_comp(drop="array_power_at_1au"))
    assert e2.value.code == "MISSING_PARAMETER"

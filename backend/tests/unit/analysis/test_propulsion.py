import math

import pytest

from app.domain.analysis.propulsion import (
    Maneuver,
    delta_v_ms,
    maneuver_budget,
    propellant_for_delta_v,
)
from app.domain.errors import DomainValidationError
from app.schemas.catalog import CatalogComponent

PROV = {"fidelity": "gameplay-estimate", "source_name": "t", "assumptions": ["t"]}


def prop(isp: float = 300.0, cap: float = 200.0, tags: tuple[str, ...] = ()) -> CatalogComponent:
    def q(v: float, u: str) -> dict[str, object]:
        return {"value": v, "unit": u, "provenance": PROV}

    return CatalogComponent.model_validate(
        {
            "id": "p", "name": "p", "category": "propulsion", "description": "d",
            "tags": list(tags),
            "parameters": {"isp": q(isp, "s"), "propellant_capacity": q(cap, "kg")},
            "source_record_id": "s", "provenance": PROV, "is_illustrative": True,
        }
    )  # fmt: skip


def test_delta_v_isp300_ratio2() -> None:
    assert delta_v_ms(300.0, 200.0, 100.0) == pytest.approx(2039.2, abs=0.5)


def test_inverse_propellant() -> None:
    assert propellant_for_delta_v(300.0, 100.0, 2039.2) == pytest.approx(100.0, abs=0.1)


def test_roundtrip() -> None:
    p = propellant_for_delta_v(220.0, 50.0, 800.0)
    assert delta_v_ms(220.0, 50.0 + p, 50.0) == pytest.approx(800.0)


@pytest.mark.parametrize(
    ("isp", "m0", "mf", "field"),
    [
        (300.0, 100.0, 100.0, "m0_kg"),
        (300.0, 90.0, 100.0, "m0_kg"),
        (0.0, 200.0, 100.0, "isp_s"),
        (-1.0, 200.0, 100.0, "isp_s"),
        (300.0, 200.0, 0.0, "mf_kg"),
        (300.0, 200.0, -5.0, "mf_kg"),
        (math.nan, 200.0, 100.0, "isp_s"),
    ],
)
def test_delta_v_invalid(isp: float, m0: float, mf: float, field: str) -> None:
    with pytest.raises(DomainValidationError) as e:
        delta_v_ms(isp, m0, mf)
    assert e.value.field == field


@pytest.mark.parametrize(
    ("isp", "mf", "dv", "field"),
    [(0.0, 100.0, 10.0, "isp_s"), (300.0, 0.0, 10.0, "mf_kg"), (300.0, 100.0, 0.0, "dv_ms")],
)
def test_propellant_invalid(isp: float, mf: float, dv: float, field: str) -> None:
    with pytest.raises(DomainValidationError) as e:
        propellant_for_delta_v(isp, mf, dv)
    assert e.value.field == field


def test_budget_available_uses_physical_masses() -> None:
    b = maneuver_budget(prop(), 100.0, [], 0.0, propellant_kg=100.0)
    assert b.available_ms == pytest.approx(2039.2, abs=0.5)
    assert b.required_ms == 0.0
    assert b.provenance.fidelity == "derived"
    assert b.model_id == "propulsion-v1"
    assert b.reserve_consumed_by is None


def test_trajectory_info_not_counted() -> None:
    base = [Maneuver("tcm", 500.0, "spacecraft")]
    withinfo = [*base, Maneuver("jpl-dv-tot", 6000.0, "trajectory-info")]
    a = maneuver_budget(prop(), 100.0, base, 100.0, propellant_kg=100.0)
    b = maneuver_budget(prop(), 100.0, withinfo, 100.0, propellant_kg=100.0)
    assert b.required_ms == a.required_ms == 500.0
    assert b.margin_ms == a.margin_ms
    assert [m.id for m in b.informational] == ["jpl-dv-tot"]
    assert [x[0] for x in b.per_maneuver] == ["tcm"]


def test_margin_and_reserve_consumer() -> None:
    ms = [
        Maneuver("a", 1000.0, "spacecraft"),
        Maneuver("b", 800.0, "spacecraft"),
        Maneuver("c", 150.0, "spacecraft"),
    ]
    b = maneuver_budget(prop(), 100.0, ms, 200.0, propellant_kg=100.0)
    assert b.required_ms == 1950.0
    assert b.margin_ms == pytest.approx(b.available_ms - 1950.0 - 200.0)
    assert b.per_maneuver == (("a", 1000.0), ("b", 1800.0), ("c", 1950.0))
    # available ~2039; usable = ~1839; cumulative first exceeds at "c" (1950)
    assert b.reserve_consumed_by == "c"


def test_no_reserve_consumption_when_within() -> None:
    b = maneuver_budget(
        prop(), 100.0, [Maneuver("a", 100.0, "spacecraft")], 50.0, propellant_kg=100.0
    )
    assert b.reserve_consumed_by is None
    assert b.margin_ms > 0


def test_low_thrust_warning() -> None:
    b = maneuver_budget(prop(tags=("low-thrust",)), 100.0, [], 0.0, propellant_kg=100.0)
    assert any("long burn durations not modelled" in a for a in b.assumptions)
    b2 = maneuver_budget(prop(tags=("high-thrust",)), 100.0, [], 0.0, propellant_kg=100.0)
    assert not any("long burn" in a for a in b2.assumptions)


def test_propellant_exceeds_capacity() -> None:
    with pytest.raises(DomainValidationError) as e:
        maneuver_budget(prop(cap=50.0), 100.0, [], 0.0, propellant_kg=60.0)
    assert e.value.code == "PROPELLANT_EXCEEDS_CAPACITY"


def test_zero_propellant_gives_zero_available() -> None:
    b = maneuver_budget(prop(), 100.0, [], 0.0, propellant_kg=0.0)
    assert b.available_ms == 0.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dry_kg": 0.0},
        {"reserve_ms": -1.0},
        {"propellant_kg": -1.0},
        {"required": [Maneuver("x", -5.0, "spacecraft")]},
        {"required": [Maneuver("x", 5.0, "bogus")]},  # type: ignore[arg-type]
    ],
)
def test_budget_invalid(kwargs: dict[str, object]) -> None:
    args: dict[str, object] = {
        "dry_kg": 100.0, "required": [], "reserve_ms": 0.0, "propellant_kg": 10.0,
    }  # fmt: skip
    args.update(kwargs)
    with pytest.raises(DomainValidationError):
        maneuver_budget(
            prop(), args["dry_kg"], args["required"], args["reserve_ms"],  # type: ignore[arg-type]
            propellant_kg=args["propellant_kg"],  # type: ignore[arg-type]
        )


def test_missing_isp_parameter() -> None:
    p = prop()
    del p.parameters["isp"]
    with pytest.raises(DomainValidationError) as e:
        maneuver_budget(p, 100.0, [], 0.0, propellant_kg=10.0)
    assert e.value.code == "MISSING_PARAMETER"


def test_wrong_unit() -> None:
    p = prop()
    p.parameters["isp"] = p.parameters["isp"].model_copy(update={"unit": "m/s"})
    with pytest.raises(DomainValidationError) as e:
        maneuver_budget(p, 100.0, [], 0.0, propellant_kg=10.0)
    assert e.value.code == "WRONG_UNIT"

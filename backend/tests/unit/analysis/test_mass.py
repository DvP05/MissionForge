import math

import pytest

from app.domain.analysis.mass import MassResult, compute_mass_budget
from app.domain.catalog.resolver import ResolvedArchitecture
from app.domain.errors import DomainValidationError
from app.schemas.catalog import CatalogComponent

PROV = {"fidelity": "gameplay-estimate", "source_name": "t", "assumptions": ["t"]}


def comp(cid: str, cat: str, params: dict[str, float]) -> CatalogComponent:
    return CatalogComponent.model_validate(
        {
            "id": cid, "name": cid, "category": cat, "description": "d",
            "parameters": {
                k: {"value": v, "unit": "kg", "provenance": PROV} for k, v in params.items()
            },
            "source_record_id": "s", "provenance": PROV, "is_illustrative": True,
        }
    )  # fmt: skip


def arch(
    instruments: tuple[CatalogComponent, ...] | None = None,
    bus_mass: float = 40.0,
    structure: float = 20.0,
) -> ResolvedArchitecture:
    # subsystems: bus 40 + prop dry 15 + power 10 + adcs 8 + comms 7 + thermal 5 + cdh 5 = 90
    if instruments is None:
        instruments = (comp("inst", "instrument", {"mass": 10.0}),)
    return ResolvedArchitecture(
        launch=comp("l", "launch", {}),
        bus=comp("bus", "bus", {"mass": bus_mass, "structure_mass": structure}),
        propulsion=comp("prop", "propulsion", {"dry_mass": 15.0, "propellant_capacity": 500.0}),
        power=comp("pow", "power", {"mass": 10.0}),
        adcs=comp("adcs", "adcs", {"mass": 8.0}),
        communications=comp("comm", "communications", {"mass": 7.0}),
        thermal=comp("therm", "thermal", {"mass": 5.0}),
        cdh=comp("cdh", "cdh", {"mass": 5.0}),
        ground=comp("g", "ground", {}),
        instruments=instruments,
    )


def test_budget_numbers() -> None:
    r = compute_mass_budget(arch(), 40.0, 0.2, None)
    assert isinstance(r, MassResult)
    assert r.payload_kg == pytest.approx(10.0)
    assert r.subsystem_dry_kg == pytest.approx(90.0)
    assert r.dry_kg == pytest.approx(100.0)
    assert r.wet_kg == pytest.approx(140.0)
    assert r.allocated_kg == pytest.approx(168.0)
    assert r.margin_to_limit_fraction is None
    assert r.model_id == "mass-v1"
    assert r.provenance.fidelity == "derived"
    assert r.assumptions


def test_margin_to_limit() -> None:
    assert compute_mass_budget(arch(), 40.0, 0.2, 200.0).margin_to_limit_fraction == pytest.approx(
        0.16
    )
    assert compute_mass_budget(arch(), 40.0, 0.2, 150.0).margin_to_limit_fraction == pytest.approx(
        -0.12
    )


def test_instrument_quantity_doubles_mass() -> None:
    i = comp("inst", "instrument", {"mass": 10.0})
    r = compute_mass_budget(arch((i, i)), 40.0, 0.2, None)
    assert r.payload_kg == pytest.approx(20.0)
    assert r.dry_kg == pytest.approx(110.0)
    assert dict(r.top_contributors)["inst"] == pytest.approx(20.0)


def test_top_contributors_cover_80_percent_descending() -> None:
    r = compute_mass_budget(arch(), 40.0, 0.2, None)
    kgs = [kg for _, kg in r.top_contributors]
    assert kgs == sorted(kgs, reverse=True)
    assert sum(kgs) >= 0.8 * r.wet_kg
    assert r.top_contributors[0] == ("bus", 40.0)
    assert r.top_contributors[1] == ("propellant", 40.0)  # tie by id: bus < propellant
    assert len(r.top_contributors) < 8  # a prefix, not everything


def test_no_hidden_structure_factor() -> None:
    a = compute_mass_budget(arch(structure=20.0), 40.0, 0.2, None)
    b = compute_mass_budget(arch(structure=0.0), 40.0, 0.2, None)
    assert a.dry_kg == b.dry_kg == pytest.approx(100.0)


def test_no_instruments_gives_zero_payload() -> None:
    r = compute_mass_budget(arch(()), 40.0, 0.2, None)
    assert r.payload_kg == 0.0
    assert r.dry_kg == pytest.approx(90.0)


@pytest.mark.parametrize("bad", [-1.0, math.nan, math.inf])
def test_bad_scalars_rejected(bad: float) -> None:
    with pytest.raises(DomainValidationError):
        compute_mass_budget(arch(), bad, 0.2, None)
    with pytest.raises(DomainValidationError):
        compute_mass_budget(arch(), 40.0, bad, None)
    with pytest.raises(DomainValidationError):
        compute_mass_budget(arch(), 40.0, 0.2, bad)


def test_zero_limit_rejected() -> None:
    with pytest.raises(DomainValidationError):
        compute_mass_budget(arch(), 40.0, 0.2, 0.0)


@pytest.mark.parametrize("bad", [-5.0, math.nan])
def test_bad_component_mass_rejected(bad: float) -> None:
    c = comp("inst", "instrument", {"mass": 10.0})
    broken = CatalogComponent.model_construct(
        **{**c.__dict__, "parameters": {"mass": c.parameters["mass"].model_construct(
            **{**c.parameters["mass"].__dict__, "value": bad})}}
    )  # fmt: skip
    with pytest.raises(DomainValidationError) as e:
        compute_mass_budget(arch((broken,)), 40.0, 0.2, None)
    assert e.value.field.startswith("inst")


def test_missing_mass_parameter_rejected() -> None:
    with pytest.raises(DomainValidationError) as e:
        compute_mass_budget(arch((comp("inst", "instrument", {}),)), 40.0, 0.2, None)
    assert e.value.code == "MISSING_PARAMETER"


def test_wrong_unit_rejected() -> None:
    c = CatalogComponent.model_validate(
        {
            "id": "inst", "name": "i", "category": "instrument", "description": "d",
            "parameters": {"mass": {"value": 1.0, "unit": "W", "provenance": PROV}},
            "source_record_id": "s", "provenance": PROV,
        }
    )  # fmt: skip
    with pytest.raises(DomainValidationError) as e:
        compute_mass_budget(arch((c,)), 40.0, 0.2, None)
    assert e.value.code == "WRONG_UNIT"

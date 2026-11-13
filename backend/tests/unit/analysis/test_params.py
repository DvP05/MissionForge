import math

import pytest

from app.domain.analysis._params import derived_provenance, param_value
from app.domain.errors import DomainValidationError
from app.schemas.catalog import CatalogComponent

PROV = {"fidelity": "gameplay-estimate", "source_name": "t", "assumptions": ["t"]}


def comp(value: float = 2.0, unit: str = "kg") -> CatalogComponent:
    return CatalogComponent.model_validate(
        {
            "id": "c", "name": "c", "category": "cdh", "description": "d", "tags": [],
            "parameters": {"mass": {"value": value, "unit": unit, "provenance": PROV}},
            "source_record_id": "s", "provenance": PROV, "is_illustrative": True,
        }
    )  # fmt: skip


def test_param_value_ok() -> None:
    assert param_value(comp(), "mass", "kg", field="c.mass") == 2.0


def test_missing_parameter() -> None:
    with pytest.raises(DomainValidationError) as e:
        param_value(comp(), "nope", "kg", field="c.nope")
    assert e.value.code == "MISSING_PARAMETER"


def test_wrong_unit() -> None:
    with pytest.raises(DomainValidationError) as e:
        param_value(comp(unit="W"), "mass", "kg", field="c.mass")
    assert e.value.code == "WRONG_UNIT"


def test_derived_provenance() -> None:
    p = derived_provenance("src", ("a",))
    assert p.fidelity == "derived" and p.source_name == "src" and list(p.assumptions) == ["a"]
    assert math.isfinite(1.0)

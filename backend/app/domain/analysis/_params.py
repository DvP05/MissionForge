"""Shared helpers for reading catalogue parameters and labelling derived results (R14)."""

from app.domain.errors import DomainValidationError
from app.domain.units.guards import require_finite
from app.schemas.catalog import CatalogComponent
from app.schemas.units import Provenance


def param_value(component: CatalogComponent, key: str, unit: str, *, field: str) -> float:
    """Return the finite value of ``component.parameters[key]``, checking its unit."""
    q = component.parameters.get(key)
    if q is None:
        raise DomainValidationError("MISSING_PARAMETER", field, f"{field} is required")
    if q.unit != unit:
        raise DomainValidationError("WRONG_UNIT", field, f"{field} must be in {unit}")
    return require_finite(q.value, field)


def derived_provenance(source_name: str, assumptions: tuple[str, ...]) -> Provenance:
    return Provenance(fidelity="derived", source_name=source_name, assumptions=assumptions)

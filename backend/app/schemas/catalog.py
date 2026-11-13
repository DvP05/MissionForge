"""Catalogue record contracts (architecture 6.3). Owner: data/domain lead."""

from typing import Literal

from pydantic import Field, StrictBool, StrictInt

from app.schemas.api import ContractModel
from app.schemas.units import Provenance, Quantity, UnitFraction

ComponentCategory = Literal[
    "launch", "bus", "propulsion", "power", "adcs", "communications",
    "thermal", "cdh", "instrument", "ground",
]  # fmt: skip


class FailureMode(ContractModel):
    id: str
    description: str
    base_probability: UnitFraction
    affected_metric: str
    severity: StrictInt = Field(ge=1, le=5)
    mitigation_ids: list[str] = Field(default_factory=list)


class CompatibilityRule(ContractModel):
    category: str
    ids: list[str] | None = None
    tags: list[str] | None = None


class CatalogComponent(ContractModel):
    id: str
    name: str
    category: ComponentCategory
    description: str
    tags: list[str] = Field(default_factory=list)
    parameters: dict[str, Quantity]
    capabilities: list[str] = Field(default_factory=list)
    compatible_with: list[CompatibilityRule] = Field(default_factory=list)
    failure_modes: list[FailureMode] = Field(default_factory=list)
    source_record_id: str
    provenance: Provenance
    is_illustrative: StrictBool = False

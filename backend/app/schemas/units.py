"""Units, provenance and Quantity contract (architecture 6.2)."""

import math
from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.api import ContractModel

Fidelity = Literal["source-backed", "derived", "gameplay-estimate", "not-modelled"]
Unit = Literal[
    "kg", "m", "s", "day", "km", "km/s", "m/s", "W", "Wh", "J",
    "bit/s", "bit", "Hz", "dB", "dBW", "K", "USD", "USD_2026", "%", "rad", "deg",
]  # fmt: skip


class Provenance(ContractModel):
    fidelity: Fidelity
    source_name: str
    source_url: str | None = None
    source_version: str | None = None
    retrieved_at: datetime | None = None
    published_at: date | None = None
    assumptions: list[str] = Field(default_factory=list)
    notes: str | None = None


class Uncertainty(ContractModel):
    distribution: Literal["normal", "uniform", "triangular", "interval"]
    min: float | None = Field(default=None, strict=True)
    mode: float | None = Field(default=None, strict=True)
    max: float | None = Field(default=None, strict=True)
    sigma: float | None = Field(default=None, strict=True)

    @field_validator("min", "mode", "max", "sigma")
    @classmethod
    def _finite(cls, v: float | None) -> float | None:
        if v is not None and not math.isfinite(v):
            raise ValueError("must be finite")
        return v


class Quantity(ContractModel):
    value: float = Field(strict=True)
    unit: Unit
    provenance: Provenance
    uncertainty: Uncertainty | None = None

    @field_validator("value")
    @classmethod
    def _finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("value must be finite")
        return v

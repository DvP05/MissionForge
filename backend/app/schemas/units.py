"""Units, provenance and Quantity contract (architecture 6.2)."""

import math
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, Field

from app.schemas.api import ContractModel


def _require_finite(v: float) -> float:
    if not math.isfinite(v):
        raise ValueError("must be finite")
    return v


# Strict float (rejects bool/str) that also rejects NaN and +/-inf.
FiniteFloat = Annotated[float, Field(strict=True), AfterValidator(_require_finite)]

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
    min: FiniteFloat | None = None
    mode: FiniteFloat | None = None
    max: FiniteFloat | None = None
    sigma: FiniteFloat | None = None


class Quantity(ContractModel):
    value: FiniteFloat
    unit: Unit
    provenance: Provenance
    uncertainty: Uncertainty | None = None

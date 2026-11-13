"""Destination and trajectory selection contracts (architecture 6.2)."""

from datetime import date
from typing import Literal

from app.schemas.api import ContractModel
from app.schemas.units import FiniteFloat, Provenance


class Destination(ContractModel):
    body_id: str
    name: str
    body_type: str
    source: Provenance | None = None


class TrajectorySelection(ContractModel):
    provider: Literal["jpl-mdesign", "scenario-preset", "manual-estimate"]
    option_id: str
    departure_date: date
    arrival_date: date | None = None
    time_of_flight_days: FiniteFloat | None = None
    c3_km2_per_s2: FiniteFloat | None = None
    departure_v_infinity_km_per_s: FiniteFloat | None = None
    arrival_v_infinity_km_per_s: FiniteFloat | None = None
    mission_delta_v_km_per_s: FiniteFloat | None = None
    raw_source_ref: str | None = None

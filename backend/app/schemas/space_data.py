"""JPL Small-Body Mission Design contracts (architecture 10.4, Phase 5, module M17).

Only normalised fields reach the client; raw JPL payloads stay server-side. Values keep the
JPL units (km/s, km^2/s^2, days) and are converted at the domain boundary.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import Field, StrictBool, StrictInt

from app.schemas.api import ContractModel
from app.schemas.units import FiniteFloat, Provenance

SourceStatus = Literal["live", "cached", "demo"]


class JplMissionOption(ContractModel):
    designation: str
    name: str
    departure_date: date
    arrival_date: date
    c3_km2_per_s2: FiniteFloat
    departure_v_infinity_km_per_s: FiniteFloat
    arrival_v_infinity_km_per_s: FiniteFloat
    total_delta_v_km_per_s: FiniteFloat
    time_of_flight_days: FiniteFloat
    orbit_class: str
    absolute_magnitude: FiniteFloat | None = None
    orbit_condition_code: FiniteFloat | None = None
    is_near_earth_object: StrictBool
    is_potentially_hazardous: StrictBool
    is_binary: StrictBool
    # Server-side reference the client stores in TrajectorySelection.raw_source_ref; the
    # server verifies it before any value is shown as source-backed (R36 / R48).
    source_ref: str
    source: Provenance


class SourceInfo(ContractModel):
    status: SourceStatus
    synthetic: StrictBool  # True: bundled synthetic fixture, NOT JPL data
    retrieved_at: datetime | None = None
    signature_version: str | None = None
    note: str
    skipped_rows: StrictInt = Field(default=0, ge=0)


class NeoAccessibleData(ContractModel):
    options: list[JplMissionOption]
    source: SourceInfo


class NeoDetailData(ContractModel):
    designation: str
    options: list[JplMissionOption]
    source: SourceInfo

"""MissionState and related contracts (architecture 6.2).

MissionState is the single editable source of truth. It stores no derived totals.
"""

from datetime import datetime
from typing import Literal

from pydantic import Field, StrictBool, StrictInt, StrictStr, field_validator

from app.schemas.api import ContractModel
from app.schemas.trajectory import Destination, TrajectorySelection
from app.schemas.units import FiniteFloat, Quantity

SCHEMA_VERSION = "1.0"
MAX_TITLE_LENGTH = 80


class ValidationIssue(ContractModel):
    code: str
    path: str
    message: str


class MeasurementRequirement(ContractModel):
    id: str
    description: str
    instrument_capability: str
    target_threshold: Quantity | None = None
    coverage_weight: FiniteFloat = Field(ge=0)
    required: bool = True


class ScienceObjective(ContractModel):
    id: str
    title: str
    question: str
    priority: FiniteFloat = Field(gt=0)
    required_measurements: list[MeasurementRequirement]


class ComponentSelection(ContractModel):
    component_id: str
    quantity: StrictInt = Field(gt=0)
    enabled: bool = True
    overrides: dict[str, FiniteFloat | StrictStr | StrictBool] = Field(default_factory=dict)


class SpacecraftArchitecture(ContractModel):
    launch_vehicle_id: str
    bus_id: str
    propulsion_id: str
    power_id: str
    adcs_id: str
    communications_id: str
    thermal_id: str
    cdh_id: str
    instrument_ids: list[str]
    ground_segment_id: str


class ObservationPlanItem(ContractModel):
    measurement_id: str
    start_day: FiniteFloat = Field(ge=0)
    duration_hours: FiniteFloat = Field(gt=0)
    duty_cycle: FiniteFloat = Field(ge=0, le=1)


class DownlinkPlanItem(ContractModel):
    start_day: FiniteFloat = Field(ge=0)
    duration_minutes: FiniteFloat = Field(gt=0)
    data_rate_bits_per_second: FiniteFloat = Field(gt=0)


class OperationsPlan(ContractModel):
    mission_duration_days: FiniteFloat = Field(gt=0)
    observation_plan: list[ObservationPlanItem]
    downlink_plan: list[DownlinkPlanItem]
    safe_mode_policy: Literal["conservative", "balanced", "aggressive"]
    autonomy_level: Literal["ground-led", "supervised", "autonomous"]


class MissionConstraints(ContractModel):
    maximum_budget_usd: FiniteFloat = Field(gt=0)
    launch_mass_limit_kg: FiniteFloat | None = Field(default=None, gt=0)
    minimum_science_score: FiniteFloat | None = None
    minimum_success_probability: FiniteFloat | None = Field(default=None, ge=0, le=1)
    mass_margin_fraction: FiniteFloat = Field(ge=0)
    power_margin_fraction: FiniteFloat = Field(ge=0)
    data_margin_fraction: FiniteFloat = Field(ge=0)
    delta_v_margin_km_per_s: FiniteFloat = Field(ge=0)


class MissionState(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    mission_id: str
    title: str
    scenario_id: Literal["neo-rendezvous", "lunar-polar-scout", "earth-observation"]
    created_at: datetime
    updated_at: datetime
    design_revision: StrictInt = Field(ge=0)
    science_objectives: list[ScienceObjective]
    destination: Destination
    trajectory: TrajectorySelection
    architecture: SpacecraftArchitecture
    operations: OperationsPlan
    constraints: MissionConstraints
    random_seed: StrictInt

    @field_validator("title")
    @classmethod
    def _sanitize_title(cls, v: str) -> str:
        # Local import: domain.mission.validation imports this module.
        from app.domain.mission.validation import sanitize_title

        return sanitize_title(v)

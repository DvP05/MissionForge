"""Derived engineering analysis contracts (architecture 6.4, 7.10, 7.11). Owner: domain lead.

MissionAnalysis is regenerated from MissionState; it is never edited. Hard feasibility is
separate from the weighted score: `mission_ready` can never be true for an infeasible
design or while any constraint has status "fail".
"""

from datetime import datetime
from typing import Literal, Self

from pydantic import Field, StrictBool, StrictInt, model_validator

from app.schemas.api import ContractModel
from app.schemas.units import FiniteFloat, NonNegativeFloat, Quantity, UnitFraction

ConstraintStatus = Literal["pass", "warning", "fail", "not-modelled"]
Feasibility = Literal["feasible", "marginal", "infeasible"]
ScoreDimensionId = Literal[
    "scientific-return",
    "mission-execution",
    "engineering-robustness",
    "resource-stewardship",
    "operations-quality",
]


class SuggestedAction(ContractModel):
    action_id: str
    label: str
    expected_effect: str


class ConstraintResult(ContractModel):
    id: str
    label: str
    status: ConstraintStatus
    actual: Quantity | None = None
    limit: Quantity | None = None
    margin_fraction: FiniteFloat | None = None
    severity: StrictInt = Field(ge=0, le=3)
    explanation: str
    impacted_subsystems: list[str] = Field(default_factory=list)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)


class BudgetAnalysis(ContractModel):
    dry_mass_kg: Quantity
    propellant_mass_kg: Quantity
    wet_mass_kg: Quantity
    mass_margin_fraction: FiniteFloat
    average_power_w: Quantity
    peak_power_w: Quantity
    energy_margin_fraction: FiniteFloat
    data_generated_bits: Quantity
    data_downlinked_bits: Quantity
    data_margin_fraction: FiniteFloat
    required_delta_v_km_per_s: Quantity
    available_delta_v_km_per_s: Quantity
    delta_v_margin_km_per_s: FiniteFloat
    estimated_cost_usd: Quantity


class ScienceAnalysis(ContractModel):
    coverage_score: NonNegativeFloat
    weighted_objective_coverage: dict[str, UnitFraction]
    missing_requirements: list[str]
    # Spec 7.10: collected-but-not-returned science is reported separately from returned.
    collected_fraction: UnitFraction
    returned_fraction: UnitFraction


class ReliabilityAnalysis(ContractModel):
    nominal_reliability: UnitFraction
    risk_index: NonNegativeFloat
    single_point_failures: list[str]


class ScoreDimension(ContractModel):
    id: ScoreDimensionId
    weight: NonNegativeFloat
    score: FiniteFloat
    explanation: str


class ScoreBreakdown(ContractModel):
    total: FiniteFloat
    dimensions: list[ScoreDimension]


class MissionAnalysis(ContractModel):
    mission_id: str
    design_revision: StrictInt = Field(ge=0)
    engine_version: str
    catalog_version: str
    calculated_at: datetime
    budgets: BudgetAnalysis
    science: ScienceAnalysis
    reliability: ReliabilityAnalysis
    constraints: list[ConstraintResult]
    feasibility: Feasibility
    mission_ready: StrictBool
    score: ScoreBreakdown
    top_drivers: list[str]
    assumptions: list[str]

    @model_validator(mode="after")
    def _ready_requires_hard_feasibility(self) -> Self:
        if self.mission_ready and (
            self.feasibility == "infeasible" or any(c.status == "fail" for c in self.constraints)
        ):
            raise ValueError(
                "mission_ready cannot be true when feasibility is infeasible "
                "or any constraint failed"
            )
        return self

"""Derived engineering analysis contracts (architecture 6.4, 7.10, 7.11). Owner: domain lead.

MissionAnalysis is regenerated from MissionState; it is never edited. Hard feasibility is
separate from the weighted score: `mission_ready` can never be true for an infeasible
design or while any constraint has status "fail".
"""

from datetime import datetime
from typing import Literal, Self, get_args

from pydantic import Field, StrictBool, StrictInt, model_validator

from app.schemas._frozen import FrozenContract
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


class ScoreDimension(FrozenContract):
    id: ScoreDimensionId
    weight: NonNegativeFloat
    score: FiniteFloat
    explanation: str


class ScoreBreakdown(FrozenContract):
    total: FiniteFloat
    dimensions: tuple[ScoreDimension, ...]

    @model_validator(mode="after")
    def _five_unique_dimensions(self) -> Self:
        ids = [d.id for d in self.dimensions]
        if len(ids) != len(set(ids)) or set(ids) != set(get_args(ScoreDimensionId)):
            raise ValueError("dimensions must contain each of the five score dimensions once")
        return self


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
    def _hard_feasibility_is_consistent(self) -> Self:
        # Constraint status "fail" == hard failure (soft issues are "warning"), so a design
        # is infeasible exactly when at least one constraint failed (ruling R10).
        any_failed = any(c.status == "fail" for c in self.constraints)
        if any_failed and self.feasibility != "infeasible":
            raise ValueError("feasibility must be 'infeasible' when any constraint failed")
        if not any_failed and self.feasibility == "infeasible":
            raise ValueError("feasibility 'infeasible' requires at least one failed constraint")
        if self.mission_ready and self.feasibility == "infeasible":
            raise ValueError("mission_ready cannot be true for an infeasible design")
        return self

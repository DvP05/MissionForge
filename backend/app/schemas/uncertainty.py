"""Robustness-lab contracts (architecture 19.3). Owner: algorithms lead.

This is a Monte Carlo robustness proxy over simplified models, not a flight-qualified
probabilistic risk assessment. `Uncertainty.distribution == "interval"` (units.py) maps to
an epistemic `uniform` DistributionSpec (decision D4).
"""

from typing import Literal, Self

from pydantic import Field, StrictInt, model_validator

from app.schemas.api import ContractModel
from app.schemas.units import FiniteFloat, UnitFraction


class DistributionSpec(ContractModel):
    kind: Literal["normal", "uniform", "triangular"]
    mean: FiniteFloat | None = None
    std_dev: FiniteFloat | None = None
    min: FiniteFloat | None = None
    mode: FiniteFloat | None = None
    max: FiniteFloat | None = None

    @model_validator(mode="after")
    def _check_parameters(self) -> Self:
        lo, hi = self.min, self.max
        if lo is not None and hi is not None and not lo < hi:
            raise ValueError("min must be < max")
        if self.kind == "normal":
            if self.mean is None or self.std_dev is None or self.std_dev <= 0:
                raise ValueError("normal requires mean and std_dev > 0")
        elif self.kind == "uniform":
            if lo is None or hi is None:
                raise ValueError("uniform requires min and max")
        elif lo is None or hi is None or self.mode is None or not lo <= self.mode <= hi:
            raise ValueError("triangular requires min <= mode <= max")
        return self


class UncertainParameter(ContractModel):
    id: str
    path: str  # allow-listed MissionState path; never evaluate a user string
    kind: Literal["aleatory", "epistemic"]
    distribution: DistributionSpec
    rationale: str
    source_ref: str | None = None


class UncertaintyProfile(ContractModel):
    id: str
    version: str
    parameters: list[UncertainParameter]


class MetricQuantiles(ContractModel):
    p10: FiniteFloat
    median: FiniteFloat
    p90: FiniteFloat
    unit: str


class RobustnessResult(ContractModel):
    samples: StrictInt = Field(ge=0)
    seed: StrictInt
    probability_feasible: UnitFraction
    feasibility_wilson_95: tuple[UnitFraction, UnitFraction]
    metrics: dict[str, MetricQuantiles]
    failure_counts: dict[str, StrictInt]
    profile_version: str
    assumptions: list[str]
    disclaimer: str

    @model_validator(mode="after")
    def _check_interval(self) -> Self:
        lo, hi = self.feasibility_wilson_95
        if lo > hi:
            raise ValueError("feasibility_wilson_95 must be ordered (low, high)")
        if any(n < 0 for n in self.failure_counts.values()):
            raise ValueError("failure_counts must be >= 0")
        return self

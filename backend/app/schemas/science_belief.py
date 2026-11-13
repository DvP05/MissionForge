"""Science hypothesis / belief-state contracts (architecture 19.4).

Owner: algorithms lead + product owner. Hypotheses and likelihood tables are authored
scenario data (gameplay estimates), never claims about real bodies.
"""

import math
from typing import Self

from pydantic import Field, StrictInt, model_validator

from app.schemas._frozen import FrozenContract
from app.schemas.api import ContractModel
from app.schemas.units import NonNegativeFloat, UnitFraction

PROBABILITY_SUM_TOLERANCE = 1e-6


class ScienceHypothesis(ContractModel):
    id: str
    label: str
    prior_probability: UnitFraction
    description: str


class ObservationLikelihood(ContractModel):
    instrument_id: str
    outcome_id: str
    likelihood_by_hypothesis: dict[str, UnitFraction]  # P(outcome | hypothesis)


class HypothesisProbability(FrozenContract):
    hypothesis_id: str
    probability: UnitFraction


class ObservationRecord(FrozenContract):
    task_id: str
    outcome_id: str
    timestamp_mission_seconds: NonNegativeFloat


class BeliefState(FrozenContract):
    hypotheses: tuple[HypothesisProbability, ...]
    observation_history: tuple[ObservationRecord, ...]
    entropy_bits: NonNegativeFloat
    version: StrictInt = Field(ge=0)

    @model_validator(mode="after")
    def _check_distribution(self) -> Self:
        ids = [h.hypothesis_id for h in self.hypotheses]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate hypothesis_id")
        if self.hypotheses:
            total = math.fsum(h.probability for h in self.hypotheses)
            if abs(total - 1.0) > PROBABILITY_SUM_TOLERANCE:
                raise ValueError("hypothesis probabilities must sum to 1")
        return self

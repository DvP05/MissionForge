"""Bayes' rule over a small hypothesis set (architecture 19.4)."""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.errors import DomainValidationError
from app.domain.science_belief.entropy import entropy_bits
from app.schemas.science_belief import (
    BeliefState,
    HypothesisProbability,
    ObservationLikelihood,
    ObservationRecord,
    ScienceHypothesis,
)

_TOL = 1e-6


@dataclass(frozen=True)
class ScienceModel:
    """Authored scenario model: hypotheses plus P(outcome | hypothesis) per instrument."""

    scenario_id: str
    version: str
    hypotheses: tuple[ScienceHypothesis, ...]
    likelihoods: tuple[ObservationLikelihood, ...]

    def __post_init__(self) -> None:
        ids = [h.id for h in self.hypotheses]
        if not ids or len(ids) != len(set(ids)):
            raise DomainValidationError(
                "INVALID_SCIENCE_MODEL", "hypotheses", "need unique hypotheses"
            )
        if abs(math.fsum(h.prior_probability for h in self.hypotheses) - 1.0) > _TOL:
            raise DomainValidationError(
                "INVALID_SCIENCE_MODEL", "hypotheses", "priors must sum to 1"
            )
        for inst in self.instruments():
            for h in ids:
                total = math.fsum(t.likelihood_by_hypothesis.get(h, 0.0) for t in self.tables(inst))
                if abs(total - 1.0) > _TOL:
                    raise DomainValidationError(
                        "INVALID_SCIENCE_MODEL",
                        f"likelihoods.{inst}.{h}",
                        "outcome probabilities for one hypothesis must sum to 1",
                    )

    def instruments(self) -> list[str]:
        return list(dict.fromkeys(t.instrument_id for t in self.likelihoods))

    def tables(self, instrument_id: str) -> list[ObservationLikelihood]:
        return [t for t in self.likelihoods if t.instrument_id == instrument_id]

    def table(self, instrument_id: str, outcome_id: str) -> ObservationLikelihood:
        for t in self.likelihoods:
            if t.instrument_id == instrument_id and t.outcome_id == outcome_id:
                return t
        raise DomainValidationError(
            "UNKNOWN_OUTCOME", "outcomeId", f"{instrument_id} has no outcome {outcome_id!r}"
        )


def _belief(
    probs: dict[str, float], history: Sequence[ObservationRecord], version: int
) -> BeliefState:
    return BeliefState(
        hypotheses=tuple(
            HypothesisProbability(hypothesis_id=h, probability=p) for h, p in probs.items()
        ),
        observation_history=tuple(history),
        entropy_bits=entropy_bits(probs.values()),
        version=version,
    )


def initial_belief(model: ScienceModel) -> BeliefState:
    return _belief({h.id: h.prior_probability for h in model.hypotheses}, (), 0)


def posterior(probs: dict[str, float], likelihood: ObservationLikelihood) -> dict[str, float]:
    joint = {h: p * likelihood.likelihood_by_hypothesis.get(h, 0.0) for h, p in probs.items()}
    marginal = math.fsum(joint.values())
    if marginal <= 0.0:
        raise DomainValidationError(
            "IMPOSSIBLE_OBSERVATION",
            "outcomeId",
            "this outcome has zero probability under every hypothesis still possible",
        )
    return {h: v / marginal for h, v in joint.items()}


def update_belief(
    belief: BeliefState,
    likelihood: ObservationLikelihood,
    *,
    task_id: str,
    timestamp_mission_seconds: float = 0.0,
) -> BeliefState:
    """posterior(h) = prior(h) P(o|h) / sum_h' prior(h') P(o|h'). Returns a new state."""
    probs = {h.hypothesis_id: h.probability for h in belief.hypotheses}
    record = ObservationRecord(
        task_id=task_id,
        outcome_id=likelihood.outcome_id,
        timestamp_mission_seconds=timestamp_mission_seconds,
    )
    return _belief(
        posterior(probs, likelihood), (*belief.observation_history, record), belief.version + 1
    )


def outcome_probabilities(
    belief: BeliefState, tables: Sequence[ObservationLikelihood]
) -> dict[str, float]:
    """P(o | instrument, belief) = sum_h p(h) P(o | h), per outcome."""
    probs = {h.hypothesis_id: h.probability for h in belief.hypotheses}
    return {
        t.outcome_id: math.fsum(
            p * t.likelihood_by_hypothesis.get(h, 0.0) for h, p in probs.items()
        )
        for t in tables
    }

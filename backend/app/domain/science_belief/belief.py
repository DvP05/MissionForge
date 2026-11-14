"""Deterministic Bayesian updates for the bounded science tracker."""

import math
from collections.abc import Mapping, Sequence

from app.schemas.science_belief import (
    BeliefState,
    HypothesisProbability,
    ObservationLikelihood,
    ObservationRecord,
    ScienceHypothesis,
)


def _entropy(probabilities: Sequence[float]) -> float:
    return -math.fsum(p * math.log2(p) for p in probabilities if p > 0)


def initial_belief(hypotheses: Sequence[ScienceHypothesis]) -> BeliefState:
    total = math.fsum(hypothesis.prior_probability for hypothesis in hypotheses)
    if not hypotheses or total <= 0:
        raise ValueError("at least one hypothesis with positive prior is required")
    probabilities = [
        hypothesis.prior_probability / total for hypothesis in hypotheses
    ]
    return BeliefState(
        hypotheses=tuple(
            HypothesisProbability(hypothesis_id=hypothesis.id, probability=probability)
            for hypothesis, probability in zip(hypotheses, probabilities, strict=True)
        ),
        observation_history=(),
        entropy_bits=_entropy(probabilities),
        version=0,
    )


def update_belief(
    belief: BeliefState,
    likelihood: ObservationLikelihood,
    observation: ObservationRecord,
) -> BeliefState:
    """Apply P(outcome | hypothesis) and return a new normalized belief state."""
    likelihoods = likelihood.likelihood_by_hypothesis
    weights = [
        item.probability * likelihoods.get(item.hypothesis_id, 0.0)
        for item in belief.hypotheses
    ]
    evidence = math.fsum(weights)
    if evidence <= 0:
        raise ValueError("observation has zero probability under the current belief")
    probabilities = [weight / evidence for weight in weights]
    return BeliefState(
        hypotheses=tuple(
            HypothesisProbability(hypothesis_id=item.hypothesis_id, probability=probability)
            for item, probability in zip(belief.hypotheses, probabilities, strict=True)
        ),
        observation_history=belief.observation_history + (observation,),
        entropy_bits=_entropy(probabilities),
        version=belief.version + 1,
    )


def expected_information_gain(
    belief: BeliefState,
    outcomes: Mapping[str, ObservationLikelihood],
) -> float:
    """Return expected entropy reduction for a candidate observation model."""
    prior_entropy = belief.entropy_bits
    expected_posterior_entropy = 0.0
    for _outcome_id, likelihood in outcomes.items():
        probability = math.fsum(
            item.probability * likelihood.likelihood_by_hypothesis.get(item.hypothesis_id, 0.0)
            for item in belief.hypotheses
        )
        if probability <= 0:
            continue
        posterior = [
            item.probability * likelihood.likelihood_by_hypothesis.get(item.hypothesis_id, 0.0)
            / probability
            for item in belief.hypotheses
        ]
        expected_posterior_entropy += probability * _entropy(posterior)
    return max(0.0, prior_entropy - expected_posterior_entropy)

"""Expected information gain of an observation (architecture 19.4)."""

import math
from collections.abc import Iterable, Sequence

from app.domain.science_belief.bayesian_update import ScienceModel, outcome_probabilities, posterior
from app.domain.science_belief.entropy import entropy_bits
from app.schemas.science_belief import BeliefState, ObservationLikelihood


def expected_information_gain(
    belief: BeliefState, tables: Sequence[ObservationLikelihood]
) -> float:
    """EIG = H(before) - sum_o P(o) H(after o). Zero for an uninformative instrument."""
    probs = {h.hypothesis_id: h.probability for h in belief.hypotheses}
    before = entropy_bits(probs.values())
    p_o = outcome_probabilities(belief, tables)
    expected_after = math.fsum(
        p_o[t.outcome_id] * entropy_bits(posterior(probs, t).values())
        for t in tables
        if p_o[t.outcome_id] > 0
    )
    return max(0.0, before - expected_after)


def rank_observations(
    belief: BeliefState, model: ScienceModel, instrument_ids: Iterable[str]
) -> list[tuple[str, float, dict[str, float]]]:
    """(instrument, EIG bits, outcome probabilities), best first; ties by instrument id."""
    out = []
    for inst in dict.fromkeys(instrument_ids):
        tables = model.tables(inst)
        if tables:
            out.append(
                (
                    inst,
                    expected_information_gain(belief, tables),
                    outcome_probabilities(belief, tables),
                )
            )
    return sorted(out, key=lambda r: (-r[1], r[0]))

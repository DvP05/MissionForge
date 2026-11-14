"""Science hypothesis tracker (architecture 19.4, Task 6.4, module M12).

Bayesian belief over a few authored hypotheses. A tractable teaching model, not a POMDP.
Hypotheses and likelihoods are gameplay-estimate scenario data.
"""

from app.domain.science_belief.bayesian_update import (
    ScienceModel,
    initial_belief,
    outcome_probabilities,
    update_belief,
)
from app.domain.science_belief.entropy import entropy_bits
from app.domain.science_belief.expected_information_gain import (
    expected_information_gain,
    rank_observations,
)
from app.domain.science_belief.hidden_truth import draw_outcome, hidden_truth

__all__ = [
    "ScienceModel",
    "draw_outcome",
    "entropy_bits",
    "expected_information_gain",
    "hidden_truth",
    "initial_belief",
    "outcome_probabilities",
    "rank_observations",
    "update_belief",
]

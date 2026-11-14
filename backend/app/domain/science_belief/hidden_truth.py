"""Seeded hidden scenario truth and simulated outcomes (architecture 19.4).

The truth is derived from the mission seed only on the server, and must never be put in
an API payload while a mission is running.
"""

import hashlib
import random

from app.domain.science_belief.bayesian_update import ScienceModel


def _rng(*parts: object) -> random.Random:
    digest = hashlib.sha256(":".join(str(p) for p in parts).encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def hidden_truth(model: ScienceModel, seed: int) -> str:
    """Draw the true hypothesis from the priors with the scenario seed."""
    rng = _rng("truth", model.scenario_id, model.version, seed)
    ids = [h.id for h in model.hypotheses]
    return rng.choices(ids, weights=[h.prior_probability for h in model.hypotheses], k=1)[0]


def draw_outcome(model: ScienceModel, seed: int, instrument_id: str, index: int) -> str:
    """Outcome of the `index`-th observation with `instrument_id`, given the hidden truth."""
    truth = hidden_truth(model, seed)
    tables = model.tables(instrument_id)
    rng = _rng("outcome", model.scenario_id, seed, instrument_id, index)
    weights = [t.likelihood_by_hypothesis.get(truth, 0.0) for t in tables]
    return rng.choices([t.outcome_id for t in tables], weights=weights, k=1)[0]

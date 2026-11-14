"""Bayesian belief, entropy and expected information gain (Task 6.4, architecture 19.4)."""

import math
import time

import pytest

from app.domain.errors import DomainValidationError
from app.domain.science_belief import (
    ScienceModel,
    draw_outcome,
    entropy_bits,
    expected_information_gain,
    hidden_truth,
    initial_belief,
    rank_observations,
    update_belief,
)
from app.schemas.science_belief import ObservationLikelihood, ScienceHypothesis
from app.services.science_service import load_science_models


def _model(priors: tuple[float, ...] = (1 / 3, 1 / 3, 1 / 3)) -> ScienceModel:
    hs = tuple(
        ScienceHypothesis(id=h, label=h, prior_probability=p, description=h)
        for h, p in zip(("a", "b", "c"), priors, strict=True)
    )
    tables = (
        ObservationLikelihood(
            instrument_id="spec",
            outcome_id="x",
            likelihood_by_hypothesis={"a": 0.7, "b": 0.2, "c": 0.1},
        ),
        ObservationLikelihood(
            instrument_id="spec",
            outcome_id="y",
            likelihood_by_hypothesis={"a": 0.3, "b": 0.8, "c": 0.9},
        ),
        ObservationLikelihood(
            instrument_id="flat",
            outcome_id="u",
            likelihood_by_hypothesis={"a": 0.5, "b": 0.5, "c": 0.5},
        ),
        ObservationLikelihood(
            instrument_id="flat",
            outcome_id="v",
            likelihood_by_hypothesis={"a": 0.5, "b": 0.5, "c": 0.5},
        ),
    )
    return ScienceModel("t", "1", hs, tables)


def _probs(belief) -> list[float]:  # type: ignore[no-untyped-def]
    return [h.probability for h in belief.hypotheses]


def test_uniform_prior_posterior_equals_likelihood() -> None:
    m = _model()
    post = update_belief(initial_belief(m), m.table("spec", "x"), task_id="t1")
    assert _probs(post) == pytest.approx([0.7, 0.2, 0.1], abs=1e-12)
    assert math.fsum(_probs(post)) == pytest.approx(1.0, abs=1e-12)
    assert post.version == 1 and post.observation_history[0].outcome_id == "x"


def test_more_likely_outcome_raises_that_hypothesis() -> None:
    m = _model()
    b0 = initial_belief(m)
    b1 = update_belief(b0, m.table("spec", "x"), task_id="t")
    assert _probs(b1)[0] > _probs(b0)[0]
    assert _probs(b1)[2] < _probs(b0)[2]


def test_zero_marginal_is_an_error_not_nan() -> None:
    m = _model((1.0, 0.0, 0.0))
    impossible = ObservationLikelihood(
        instrument_id="spec",
        outcome_id="z",
        likelihood_by_hypothesis={"a": 0.0, "b": 1.0, "c": 1.0},
    )
    with pytest.raises(DomainValidationError) as err:
        update_belief(initial_belief(m), impossible, task_id="t")
    assert err.value.code == "IMPOSSIBLE_OBSERVATION"


def test_entropy_values() -> None:
    assert entropy_bits([0.5, 0.5]) == 1.0
    assert entropy_bits([1.0, 0.0]) == 0.0
    assert entropy_bits([0.25] * 4) == pytest.approx(2.0)


def test_eig_non_negative_and_zero_when_uninformative() -> None:
    m = _model()
    b = initial_belief(m)
    assert expected_information_gain(b, m.tables("flat")) == pytest.approx(0.0, abs=1e-12)
    assert expected_information_gain(b, m.tables("spec")) > 0
    ranked = rank_observations(b, m, ["flat", "spec", "missing"])
    assert [r[0] for r in ranked] == ["spec", "flat"]
    assert all(r[1] >= -1e-12 for r in ranked)


def test_bad_models_rejected() -> None:
    with pytest.raises(DomainValidationError):
        _model((0.5, 0.5, 0.5))
    hs = _model().hypotheses
    broken = (
        ObservationLikelihood(
            instrument_id="i",
            outcome_id="o",
            likelihood_by_hypothesis={"a": 0.4, "b": 1.0, "c": 1.0},
        ),
    )
    with pytest.raises(DomainValidationError):
        ScienceModel("t", "1", hs, broken)
    with pytest.raises(DomainValidationError):
        _model().table("spec", "nope")


def test_shipped_neo_model_is_valid_and_deterministic_truth() -> None:
    model = load_science_models()["neo-rendezvous"]
    assert len(model.hypotheses) == 3
    assert hidden_truth(model, 42) == hidden_truth(model, 42)
    truths = {hidden_truth(model, s) for s in range(60)}
    assert truths == {h.id for h in model.hypotheses}
    o = draw_outcome(model, 42, "inst-vnir-spectrometer", 0)
    assert o == draw_outcome(model, 42, "inst-vnir-spectrometer", 0)
    assert o in {t.outcome_id for t in model.tables("inst-vnir-spectrometer")}


def test_update_under_one_millisecond() -> None:
    m = load_science_models()["neo-rendezvous"]
    b = initial_belief(m)
    t = m.table("inst-vnir-spectrometer", "hydration-band")
    start = time.perf_counter()
    for _ in range(1000):
        update_belief(b, t, task_id="x")
    assert (time.perf_counter() - start) / 1000 < 0.001

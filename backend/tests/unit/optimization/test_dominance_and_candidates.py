"""Dominance, Pareto front and candidate generation (Task 6.2, architecture 19.2 / 21)."""

import pytest

from app.domain.errors import DomainValidationError
from app.domain.optimization import (
    MAX_CANDIDATES,
    candidate_id,
    dominates,
    generate_candidates,
    pareto_front,
)

from ..architecture_graph._support import catalog, state


def test_dominates_requires_no_worse_and_one_better() -> None:
    assert dominates([1, 2, 3], [1, 2, 4])
    assert dominates([0, 0], [1, 1])
    assert not dominates([1, 2, 3], [1, 2, 3])  # identical vectors
    assert not dominates([1, 5], [2, 4])  # trade-off
    assert not dominates([2, 4], [1, 5])
    with pytest.raises(DomainValidationError):
        dominates([1], [1, 2])


def test_pareto_front_keeps_trade_offs_and_ties() -> None:
    vectors = {"a": [1.0, 5.0], "b": [2.0, 4.0], "c": [3.0, 6.0], "d": [1.0, 5.0]}
    assert pareto_front(vectors) == ["a", "b", "d"]


def test_candidate_pool_is_bounded_unique_and_deterministic() -> None:
    s = state()
    a = generate_candidates(s, catalog(), seed=42, cap=MAX_CANDIDATES)
    b = generate_candidates(s, catalog(), seed=42, cap=MAX_CANDIDATES)
    assert len(a) == MAX_CANDIDATES
    assert [c.id for c in a] == [c.id for c in b]
    assert len({c.id for c in a}) == len(a)
    assert a[0].generation == 0 and a[0].state == s
    assert all(c.id == candidate_id(c.state.architecture) for c in a)
    assert {c.generation for c in a} >= {0, 1, 2, 3}
    other = generate_candidates(s, catalog(), seed=7, cap=MAX_CANDIDATES)
    assert [c.id for c in other] != [c.id for c in a]


def test_every_candidate_keeps_an_instrument_and_valid_parts() -> None:
    for c in generate_candidates(state(), catalog(), seed=1, cap=MAX_CANDIDATES):
        arch = c.state.architecture
        assert arch.instrument_ids
        assert all(catalog().get(i) is not None for i in arch.instrument_ids)
        assert catalog()[arch.communications_id].category == "communications"


def test_cap_bounds() -> None:
    with pytest.raises(DomainValidationError):
        generate_candidates(state(), catalog(), seed=1, cap=0)
    with pytest.raises(DomainValidationError):
        generate_candidates(state(), catalog(), seed=1, cap=MAX_CANDIDATES + 1)
    assert len(generate_candidates(state(), catalog(), seed=1, cap=5)) == 5


def test_margin_proxy_skips_undefined_margins() -> None:
    """R38: None margins are ignored by the resilient proxy, never read as 0."""
    from app.domain.optimization.select_archetypes import margin_proxy

    from ..architecture_graph._support import analyse, state

    a = analyse(state())
    b = a.budgets
    only_mass = b.model_copy(
        update={
            "energy_margin_fraction": None,
            "data_margin_fraction": None,
            "delta_v_margin_km_per_s": None,
        }
    )
    assert margin_proxy(a.model_copy(update={"budgets": only_mass})) == b.mass_margin_fraction
    none = only_mass.model_copy(update={"mass_margin_fraction": None})
    assert margin_proxy(a.model_copy(update={"budgets": none})) == float("-inf")

"""optimize(): feasibility filter, front, archetypes, determinism, speed (Task 6.2)."""

import time
from functools import cache

import pytest

from app.domain.optimization import OBJECTIVES, dominates, optimize
from app.schemas.optimization import OptimizationResult
from app.services.robustness_service import load_profile
from app.services.template_service import TemplateService

from ..architecture_graph._support import NOW, SCENARIOS, catalog, state

TEMPLATES = TemplateService.from_directory()
KEYS = [o.key for o in OBJECTIVES]


@cache
def _result(
    scenario: str = "neo-rendezvous", seed: int = 42, samples: int = 0
) -> OptimizationResult:
    s = state(scenario)
    return optimize(
        s,
        catalog(),
        scenario=TEMPLATES.scenario_inputs(s.scenario_id),  # type: ignore[arg-type]
        seed=seed,
        cap=150,
        engine_version="0.1.0",
        now=NOW,
        profile=load_profile(),
        robustness_samples=samples,
    )


def test_objectives_are_minimised_and_unweighted() -> None:
    assert all(o.direction == "minimize" and o.weight is None for o in OBJECTIVES)
    assert KEYS == ["lifecycle_cost", "dry_mass", "negative_science_return"]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_front_is_feasible_and_non_dominated(scenario: str) -> None:
    r = _result(scenario)
    by_id = {c.id: c for c in r.candidates}
    feasible = [c for c in r.candidates if c.feasible]
    assert feasible, "every scenario should offer at least one feasible design"
    for fid in r.pareto_front_ids:
        f = by_id[fid]
        assert f.feasible
        vec = [f.objective_vector[k] for k in KEYS]
        assert not any(dominates([o.objective_vector[k] for k in KEYS], vec) for o in feasible)
    # Every feasible design off the front is dominated by something on it.
    front = [[by_id[i].objective_vector[k] for k in KEYS] for i in r.pareto_front_ids]
    for c in feasible:
        if c.id not in r.pareto_front_ids:
            assert any(dominates(v, [c.objective_vector[k] for k in KEYS]) for v in front)


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_infeasible_only_in_near_misses(scenario: str) -> None:
    r = _result(scenario)
    infeasible = {c.id for c in r.candidates if not c.feasible}
    assert set(r.near_misses) == infeasible
    assert not infeasible & set(r.pareto_front_ids)
    assert not infeasible & set(r.archetypes.values())
    for c in r.candidates:
        if not c.feasible:
            assert any(e.startswith("Near miss: fails") for e in c.explanation)


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_archetypes_optimise_their_label(scenario: str) -> None:
    r = _result(scenario)
    feasible = [c for c in r.candidates if c.feasible]
    by_id = {c.id: c for c in r.candidates}
    lean, sci = by_id[r.archetypes["lean"]], by_id[r.archetypes["science-max"]]
    assert lean.objective_vector["lifecycle_cost"] == min(
        c.objective_vector["lifecycle_cost"] for c in feasible
    )
    best = min(c.objective_vector["negative_science_return"] for c in feasible)
    assert sci.objective_vector["negative_science_return"] == best
    res = by_id[r.archetypes["resilient"]]
    assert any(e.startswith("Resilient") for e in res.explanation)


def test_resilient_uses_robustness_samples_when_asked() -> None:
    r = _result(samples=10)
    res = next(c for c in r.candidates if c.id == r.archetypes["resilient"])
    assert any("of 10 robustness samples" in e for e in res.explanation)
    proxy = _result(samples=0)
    res0 = next(c for c in proxy.candidates if c.id == proxy.archetypes["resilient"])
    assert any("(proxy)" in e for e in res0.explanation)


def test_same_input_same_output() -> None:
    a = _result.__wrapped__("neo-rendezvous", 42, 0)
    b = _result.__wrapped__("neo-rendezvous", 42, 0)
    assert a.model_dump_json() == b.model_dump_json()


def test_at_least_100_candidates_on_neo_default() -> None:
    assert len(_result().candidates) >= 100


def test_250_candidates_under_three_seconds() -> None:
    s = state()
    start = time.perf_counter()
    r = optimize(
        s,
        catalog(),
        scenario=TEMPLATES.scenario_inputs(s.scenario_id),  # type: ignore[arg-type]
        seed=3,
        cap=250,
        engine_version="0.1.0",
        now=NOW,
    )
    assert len(r.candidates) == 250
    assert time.perf_counter() - start < 3.0

"""Mission Analyst (Task 6.8): every number is a recomputed engine value."""

import pytest

from app.domain.analyst import MAX_RECOMMENDATIONS, apply_mutation, explain_constraint, recommend
from app.domain.errors import DomainValidationError
from app.schemas.analyst import DesignMutation
from app.services.template_service import TemplateService

from ..architecture_graph._support import (
    NOW,
    SCENARIOS,
    analyse,
    catalog,
    edit_arch,
    graph_of,
    state,
)

TEMPLATES = TemplateService.from_directory()


def _recs(s, max_n: int = 3):  # type: ignore[no-untyped-def]
    return recommend(
        s,
        analyse(s),
        catalog(),
        scenario=TEMPLATES.scenario_inputs(s.scenario_id),  # type: ignore[arg-type]
        engine_version="0.1.0",
        now=NOW,
        max_n=max_n,
    )


def test_starter_design_gets_the_radio_fix_first() -> None:
    recs = _recs(state())
    assert recs, "the starter design has a known fix"
    top = recs[0]
    assert top.mutation.kind == "swap-component"
    assert top.mutation.target == "architecture.communicationsId"
    assert top.mutation.from_value == "comms-xband-lowgain"
    assert "link-margin" in top.source_refs
    assert top.confidence_label == "high"
    assert top.metric_after["failedConstraints"] < top.metric_before["failedConstraints"]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_every_number_matches_a_fresh_engine_run(scenario: str) -> None:
    s = state(scenario)
    before = analyse(s)
    for rec in _recs(s, max_n=MAX_RECOMMENDATIONS):
        after = analyse(apply_mutation(s, rec.mutation))
        assert rec.metric_after["scoreTotal"] == after.score.total
        assert rec.metric_after["estimatedCostUsd"] == after.budgets.estimated_cost_usd.value
        assert rec.metric_after["dryMassKg"] == after.budgets.dry_mass_kg.value
        assert rec.metric_before["scoreTotal"] == before.score.total
        assert rec.mutation.kind in ("swap-component", "add-instrument", "remove-instrument")


def test_recommendations_strictly_improve_and_never_add_failures() -> None:
    for rec in _recs(state(), max_n=MAX_RECOMMENDATIONS):
        b, a = rec.metric_before, rec.metric_after
        assert a["failedConstraints"] <= b["failedConstraints"]
        assert (a["failedConstraints"], a["warningConstraints"], -a["scoreTotal"]) < (
            b["failedConstraints"],
            b["warningConstraints"],
            -b["scoreTotal"],
        )


def test_one_recommendation_per_slot() -> None:
    recs = _recs(state("lunar-polar-scout"), max_n=MAX_RECOMMENDATIONS)
    targets = [(r.mutation.target, r.mutation.from_value, r.mutation.to_value) for r in recs]
    swap_slots = [t[0] for t in targets if t[0] != "architecture.instrumentIds"]
    assert len(swap_slots) == len(set(swap_slots))


def test_already_good_design_gets_empty_list() -> None:
    fixed = edit_arch(state(), communications_id="comms-xband-medium")
    assert _recs(fixed) == []


def test_deterministic() -> None:
    assert _recs(state()) == _recs(state())


def test_apply_increments_revision_and_rejects_free_text() -> None:
    s = state()
    m = DesignMutation(
        kind="swap-component",
        target="architecture.communicationsId",
        from_value="comms-xband-lowgain",
        to_value="comms-xband-medium",
        description="x",
    )
    out = apply_mutation(s, m)
    assert out.design_revision == s.design_revision + 1
    assert out.architecture.communications_id == "comms-xband-medium"
    assert s.architecture.communications_id == "comms-xband-lowgain"  # input untouched
    bad = m.model_copy(update={"target": "__class__"})
    with pytest.raises(DomainValidationError):
        apply_mutation(s, bad)
    with pytest.raises(DomainValidationError):
        _recs(s, max_n=0)


def test_explain_constraint_gives_because_chain() -> None:
    s = state()
    lines = explain_constraint(analyse(s), graph_of(s), "link-margin")
    assert lines[0].startswith("Link margin is fail")
    assert any(line.startswith("Because") for line in lines)
    assert any(line.startswith("Try:") for line in lines)
    assert explain_constraint(analyse(s), graph_of(s), "nope") == []

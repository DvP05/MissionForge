"""Starter templates teach exactly one trade each (Task 2.9, R20).

Runs ``analyze_mission`` on every starter design and pins which constraints may
fail/warn, so a template edit cannot silently add an unrelated limit.
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from app.config import DEFAULT_CATALOG_DIR, DEFAULT_MISSIONS_DIR
from app.domain.analysis.orchestrator import (
    ENGINE_VERSION,
    analyze_mission,
    scenario_inputs_from_template,
)
from app.domain.catalog.loader import Catalog, load_catalog
from app.domain.mission.defaults import default_mission_state, list_templates
from app.schemas.analysis import ConstraintResult, MissionAnalysis
from app.schemas.mission import MissionState
from app.schemas.templates import ScenarioTemplate

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return load_catalog(DEFAULT_CATALOG_DIR)


@pytest.fixture(scope="module")
def templates() -> dict[str, ScenarioTemplate]:
    return {t.scenario_id: t for t in list_templates(DEFAULT_MISSIONS_DIR)}


def _run(
    scenario: str,
    catalog: Catalog,
    templates: dict[str, ScenarioTemplate],
    **arch: Any,
) -> tuple[MissionState, MissionAnalysis]:
    state = default_mission_state(
        scenario, mission_id="m-story", seed=1, now=NOW, templates_dir=DEFAULT_MISSIONS_DIR
    )
    dump = state.model_dump()
    dump["architecture"] = {**dump["architecture"], **arch}
    state = MissionState.model_validate(dump)
    analysis = analyze_mission(
        state,
        catalog,
        scenario=scenario_inputs_from_template(templates[scenario]),
        engine_version=ENGINE_VERSION,
        now=NOW,
    )
    return state, analysis


def _with(analysis: MissionAnalysis, *statuses: str) -> list[ConstraintResult]:
    return [c for c in analysis.constraints if c.status in statuses]


def test_neo_starter_only_link_and_data_issues(
    catalog: Catalog, templates: dict[str, ScenarioTemplate]
) -> None:
    _, a = _run("neo-rendezvous", catalog, templates)
    issues = {c.id for c in _with(a, "fail", "warning")}
    # science-* warnings are the downstream effect of the failed link (nothing returned);
    # they must never come from scheduling (see the collected-fraction check below).
    assert issues <= {
        "link-margin",
        "data-return",
        "science-mandatory-coverage",
        "science-minimum-score",
    }
    assert {"link-margin", "data-return"} & issues
    assert a.feasibility == "infeasible"
    # the required measurements are collected (scheduling is sufficient): the only shortfall
    # is that nothing is returned over the failed link
    assert a.science.returned_fraction == 0.0
    coverage = next(c for c in a.constraints if c.id == "science-mandatory-coverage")
    assert "collected but no data is returned" in coverage.explanation


def test_neo_medium_radio_is_mission_ready(
    catalog: Catalog, templates: dict[str, ScenarioTemplate]
) -> None:
    state, a = _run("neo-rendezvous", catalog, templates, communications_id="comms-xband-medium")
    assert a.feasibility == "feasible"
    assert a.mission_ready is True
    minimum = state.constraints.minimum_science_score
    assert minimum is not None and a.science.coverage_score >= minimum
    assert not _with(a, "fail", "warning")


def test_lunar_starter_one_teachable_warning(
    catalog: Catalog, templates: dict[str, ScenarioTemplate]
) -> None:
    # Teaching point: data-return (partial downlink of a larger observation campaign).
    _, a = _run("lunar-polar-scout", catalog, templates)
    assert a.feasibility == "marginal"
    assert not _with(a, "fail")
    assert [c.id for c in _with(a, "warning")] == ["data-return"]


def test_eo_starter_one_teachable_warning(
    catalog: Catalog, templates: dict[str, ScenarioTemplate]
) -> None:
    # Teaching point: data-return (a LEO ground station sees little of what the sensors make).
    state, a = _run("earth-observation", catalog, templates)
    assert a.feasibility == "marginal"
    assert not _with(a, "fail")
    assert [c.id for c in _with(a, "warning")] == ["data-return"]
    assert a.budgets.estimated_cost_usd.value <= state.constraints.maximum_budget_usd

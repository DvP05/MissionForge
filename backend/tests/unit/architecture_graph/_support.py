"""Shared fixtures for architecture-graph tests: real catalogue + scenario templates."""

from datetime import UTC, datetime
from functools import cache
from typing import Any

from app.config import DEFAULT_CATALOG_DIR, DEFAULT_MISSIONS_DIR
from app.domain.analysis.orchestrator import (
    ENGINE_VERSION,
    analyze_mission,
    scenario_inputs_from_template,
)
from app.domain.architecture_graph import build_architecture_graph
from app.domain.catalog.loader import Catalog, load_catalog
from app.domain.mission.defaults import default_mission_state, list_templates
from app.schemas.analysis import MissionAnalysis
from app.schemas.mission import MissionState
from app.schemas.optimization import ArchitectureGraph

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
SCENARIOS = ("neo-rendezvous", "lunar-polar-scout", "earth-observation")


@cache
def catalog() -> Catalog:
    return load_catalog(DEFAULT_CATALOG_DIR)


def state(scenario: str = "neo-rendezvous") -> MissionState:
    return default_mission_state(
        scenario, mission_id="m-graph", seed=42, now=NOW, templates_dir=DEFAULT_MISSIONS_DIR
    )


def analyse(s: MissionState) -> MissionAnalysis:
    templates = {t.scenario_id: t for t in list_templates(DEFAULT_MISSIONS_DIR)}
    return analyze_mission(
        s,
        catalog(),
        scenario=scenario_inputs_from_template(templates[s.scenario_id]),
        engine_version=ENGINE_VERSION,
        now=NOW,
    )


def graph_of(s: MissionState) -> ArchitectureGraph:
    return build_architecture_graph(s, analyse(s), catalog())


def edit_arch(s: MissionState, **arch: Any) -> MissionState:
    dump = s.model_dump()
    dump["architecture"] = {**dump["architecture"], **arch}
    dump["design_revision"] = s.design_revision + 1
    return MissionState.model_validate(dump)


def node(g: ArchitectureGraph, node_id: str) -> Any:
    return next(n for n in g.nodes if n.id == node_id)

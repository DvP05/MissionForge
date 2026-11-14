"""Shared fixtures for the simulation tests (Tasks 4.1, 4.2)."""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from app.config import DEFAULT_CATALOG_DIR, DEFAULT_MISSIONS_DIR, DEFAULT_SCENARIOS_DIR
from app.domain.analysis.orchestrator import (
    ENGINE_VERSION,
    ScenarioInputs,
    analyze_mission,
    scenario_inputs_from_template,
)
from app.domain.catalog.loader import Catalog, load_catalog
from app.domain.mission.defaults import default_mission_state, list_templates
from app.schemas.mission import MissionState
from app.schemas.simulation import MissionRun, SimulationInput
from app.schemas.templates import ScenarioTemplate

if TYPE_CHECKING:
    from app.domain.simulation.anomalies import ScenarioEventSet

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
EVENT_SET = "neo-rendezvous-nominal-v1"
NEO_EVENTS = "neo-default-v1"
GENERIC_EVENTS = "generic-design-v1"
SCENARIO_VERSION = "0.1.0"
APP_VERSION = "0.1.0"
MEDIUM = "comms-xband-medium"


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    return load_catalog(DEFAULT_CATALOG_DIR)


@pytest.fixture(scope="session")
def templates() -> dict[str, ScenarioTemplate]:
    return {t.scenario_id: t for t in list_templates(DEFAULT_MISSIONS_DIR)}


def make_state(scenario: str = "neo-rendezvous", seed: int = 42, **arch: Any) -> MissionState:
    state = default_mission_state(
        scenario, mission_id="m-sim", seed=seed, now=NOW, templates_dir=DEFAULT_MISSIONS_DIR
    )
    if arch:
        dump = state.model_dump()
        dump["architecture"] = {**dump["architecture"], **arch}
        state = MissionState.model_validate(dump)
    return state


SimFactory = Callable[..., tuple[SimulationInput, ScenarioInputs]]


@pytest.fixture(scope="session")
def sim_input_for(catalog: Catalog, templates: dict[str, ScenarioTemplate]) -> SimFactory:
    def build(
        state: MissionState,
        *,
        experimental: bool = False,
        seed: int | None = None,
        event_set: str = EVENT_SET,
    ) -> tuple[SimulationInput, ScenarioInputs]:
        scenario = scenario_inputs_from_template(templates[state.scenario_id])
        analysis = analyze_mission(
            state, catalog, scenario=scenario, engine_version=ENGINE_VERSION, now=NOW
        )
        sim = SimulationInput(
            mission_state=state,
            analysis=analysis,
            engine_version=ENGINE_VERSION,
            catalog_version=catalog.version,
            random_seed=state.random_seed if seed is None else seed,
            scenario_event_set_id=event_set,
            experimental=experimental,
        )
        return sim, scenario

    return build


@pytest.fixture(scope="session")
def event_sets() -> "Mapping[str, ScenarioEventSet]":
    from app.domain.simulation.anomalies import load_event_sets

    return load_event_sets(DEFAULT_SCENARIOS_DIR)


RunFactory = Callable[..., MissionRun]


@pytest.fixture(scope="session")
def run_sim(
    sim_input_for: SimFactory, catalog: Catalog, event_sets: "Mapping[str, ScenarioEventSet]"
) -> RunFactory:
    """Run a design through ``run_mission`` with the repo event sets (Task 4.2)."""
    from app.domain.simulation.runner import run_mission

    def run(
        state: MissionState,
        *,
        event_set: str = NEO_EVENTS,
        experimental: bool = False,
        seed: int | None = None,
        decisions: dict[str, str] | None = None,
    ) -> MissionRun:
        sim, scenario = sim_input_for(
            state, experimental=experimental, seed=seed, event_set=event_set
        )
        return run_mission(
            sim,
            catalog,
            scenario=scenario,
            event_sets=event_sets,
            decisions=decisions,
            scenario_version=SCENARIO_VERSION,
            app_version=APP_VERSION,
        )

    return run


def low_margin_state(seed: int = 42) -> MissionState:
    """NEO medium radio planned at its 100 kbit/s maximum: feasible, link margin ~3.7 dB."""
    dump = make_state(seed=seed, communications_id=MEDIUM).model_dump()
    dump["operations"]["downlink_plan"] = [
        {**c, "data_rate_bits_per_second": 100000.0} for c in dump["operations"]["downlink_plan"]
    ]
    return MissionState.model_validate(dump)

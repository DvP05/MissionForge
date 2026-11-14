"""Fixtures for the Evidence Passport tests (Task 4.6): real runs built through the services."""

from datetime import UTC, datetime
from typing import Any

import pytest

from app.domain.catalog.loader import Catalog
from app.main import create_app
from app.schemas.analysis import MissionAnalysis
from app.schemas.mission import MissionState
from app.schemas.simulation import MissionRun
from app.services.simulation_service import SimulationService

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
EXPORTED = datetime(2026, 11, 14, 13, 0, tzinfo=UTC)


class Env:
    def __init__(self) -> None:
        app = create_app()
        self.service: SimulationService = app.state.simulation_service
        self.catalog: Catalog = app.state.catalog_service.catalog
        self.templates = app.state.template_service

    def state(self, **changes: Any) -> MissionState:
        s = self.templates.default_mission("neo-rendezvous", seed=1, mission_id="m-doc", now=NOW)
        dump = s.model_dump()
        dump["architecture"]["communications_id"] = "comms-xband-medium"
        dump.update(changes)
        return MissionState.model_validate(dump)

    def run(self, state: MissionState | None = None, *, experimental: bool = False) -> MissionRun:
        outcome = self.service.simulate(
            state or self.state(),
            seed=42,
            event_set_id=None,
            experimental=experimental,
            decisions={},
            now=NOW,
        )
        assert outcome.stored is not None
        return outcome.stored.run

    def analysis(self, run: MissionRun) -> MissionAnalysis:
        a = self.service.run_analysis(run, NOW).analysis
        assert a is not None
        return a


@pytest.fixture(scope="session")
def env() -> Env:
    return Env()


@pytest.fixture(scope="session")
def run(env: Env) -> MissionRun:
    return env.run()

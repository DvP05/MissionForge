"""Wires the pure template functions to the default data directory and the clock."""

from datetime import UTC, datetime
from uuid import uuid4

from app.config import DEFAULT_MISSIONS_DIR
from app.domain.mission.defaults import default_mission_state, list_templates
from app.schemas.mission import MissionState
from app.schemas.templates import ScenarioTemplate


def list_scenario_templates() -> list[ScenarioTemplate]:
    return list_templates(DEFAULT_MISSIONS_DIR)


def create_default_mission(
    scenario_id: str, *, seed: int, mission_id: str | None = None
) -> MissionState:
    return default_mission_state(
        scenario_id,
        mission_id=mission_id or f"mission-{uuid4().hex[:12]}",
        seed=seed,
        now=datetime.now(UTC),
        templates_dir=DEFAULT_MISSIONS_DIR,
    )

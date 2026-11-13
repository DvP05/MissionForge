"""Scenario templates: loaded once, plus fresh default MissionStates (clock and id injected)."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.config import DEFAULT_MISSIONS_DIR
from app.domain.analysis.orchestrator import ScenarioInputs, scenario_inputs_from_template
from app.domain.mission.defaults import default_mission_state, list_templates
from app.schemas.mission import MissionState
from app.schemas.templates import ScenarioTemplate


def new_mission_id() -> str:
    return f"mission-{uuid4().hex[:12]}"


class TemplateService:
    def __init__(self, templates: list[ScenarioTemplate], templates_dir: Path) -> None:
        self._templates: dict[str, ScenarioTemplate] = {t.scenario_id: t for t in templates}
        self._dir = templates_dir

    @classmethod
    def from_directory(cls, path: Path = DEFAULT_MISSIONS_DIR) -> "TemplateService":
        return cls(list_templates(path), path)

    def list(self) -> list[ScenarioTemplate]:
        return sorted(self._templates.values(), key=lambda t: t.scenario_id)

    def get(self, scenario_id: str) -> ScenarioTemplate | None:
        return self._templates.get(scenario_id)

    def scenario_inputs(self, scenario_id: str) -> ScenarioInputs | None:
        template = self.get(scenario_id)
        return scenario_inputs_from_template(template) if template else None

    def default_mission(
        self, scenario_id: str, *, seed: int, mission_id: str, now: datetime
    ) -> MissionState:
        return default_mission_state(
            scenario_id, mission_id=mission_id, seed=seed, now=now, templates_dir=self._dir
        )


# Thin wrappers kept for the contract tests (default paths, wall clock).
def list_scenario_templates() -> list[ScenarioTemplate]:
    return list_templates(DEFAULT_MISSIONS_DIR)


def create_default_mission(
    scenario_id: str, *, seed: int, mission_id: str | None = None
) -> MissionState:
    return default_mission_state(
        scenario_id,
        mission_id=mission_id or new_mission_id(),
        seed=seed,
        now=datetime.now(UTC),
        templates_dir=DEFAULT_MISSIONS_DIR,
    )

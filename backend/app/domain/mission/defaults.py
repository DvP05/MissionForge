"""Scenario templates and the default MissionState (Task 1.5).

Pure: the templates directory and the timestamp are injected; nothing here reads the clock
or the environment. A template file is `data/missions/<scenario-id>.json`.
"""

from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from app.domain.catalog.loader import read_json
from app.domain.errors import DomainValidationError
from app.schemas.mission import MissionState
from app.schemas.templates import ScenarioTemplate


def _load(path: Path) -> ScenarioTemplate:
    try:
        return ScenarioTemplate.model_validate(read_json(path))
    except (OSError, ValueError, ValidationError) as exc:
        raise DomainValidationError("TEMPLATE_INVALID", path.name, str(exc)) from exc


def list_templates(templates_dir: Path) -> list[ScenarioTemplate]:
    """All templates in `templates_dir`, ordered by scenario id."""
    found = [_load(p) for p in sorted(templates_dir.glob("*.json"))]
    return sorted(found, key=lambda t: t.scenario_id)


def default_mission_state(
    scenario_id: str,
    *,
    mission_id: str,
    seed: int,
    now: datetime,
    templates_dir: Path | None = None,
) -> MissionState:
    """Build the starter MissionState for a scenario (design revision 0)."""
    if templates_dir is None:
        from app.config import DEFAULT_MISSIONS_DIR  # noqa: PLC0415  (default path only)

        templates_dir = DEFAULT_MISSIONS_DIR
    for template in list_templates(templates_dir):
        if template.scenario_id == scenario_id:
            return MissionState.model_validate(
                {
                    **template.mission_state.model_dump(),
                    "mission_id": mission_id,
                    "created_at": now,
                    "updated_at": now,
                    "design_revision": 0,
                    "random_seed": seed,
                }
            )
    raise DomainValidationError(
        "UNKNOWN_SCENARIO", "scenarioId", f"unknown scenario {scenario_id!r}"
    )

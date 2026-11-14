"""Robustness lab orchestration (Task 6.3). Owns the profile file I/O; no HTTP types."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.domain.uncertainty import run_robustness
from app.schemas.mission import MissionState
from app.schemas.uncertainty import RobustnessResult, UncertaintyProfile
from app.services.catalog_service import CatalogService
from app.services.mission_service import MissionService, ValidationOutcome
from app.services.template_service import TemplateService

# <repo>/data/uncertainty/default_profile.json (services -> app -> backend -> repo).
DEFAULT_PROFILE_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "uncertainty" / "default_profile.json"
)


def load_profile(path: Path = DEFAULT_PROFILE_PATH) -> UncertaintyProfile:
    return UncertaintyProfile.model_validate(json.loads(path.read_text(encoding="utf-8")))


@dataclass(frozen=True)
class RobustnessOutcome:
    result: RobustnessResult | None = None
    failure: ValidationOutcome | None = None


class RobustnessService:
    def __init__(
        self,
        missions: MissionService,
        catalogs: CatalogService,
        templates: TemplateService,
        engine_version: str,
        profile: UncertaintyProfile,
    ) -> None:
        self._missions = missions
        self._catalogs = catalogs
        self._templates = templates
        self._engine_version = engine_version
        self.profile = profile

    def run(
        self, state: MissionState, *, samples: int, seed: int, now: datetime
    ) -> RobustnessOutcome:
        """Validate the design, then run the seeded robustness sweep on copies of it."""
        outcome = self._missions.validate(state, now)
        if outcome.analysis is None:
            return RobustnessOutcome(failure=outcome)
        scenario = self._templates.scenario_inputs(state.scenario_id)
        if scenario is None:
            raise LookupError(f"no template for scenario {state.scenario_id!r}")
        result = run_robustness(
            state,
            self.profile,
            self._catalogs.catalog,
            scenario=scenario,
            n=samples,
            seed=seed,
            engine_version=self._engine_version,
            now=now,
        )
        return RobustnessOutcome(result=result)

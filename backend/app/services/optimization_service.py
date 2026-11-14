"""Mission Design Arena orchestration (Task 6.2). No HTTP types here."""

from dataclasses import dataclass
from datetime import datetime

from app.domain.optimization import optimize
from app.schemas.mission import MissionState
from app.schemas.optimization import OptimizationResult
from app.schemas.uncertainty import UncertaintyProfile
from app.services.catalog_service import CatalogService
from app.services.mission_service import MissionService, ValidationOutcome
from app.services.template_service import TemplateService


@dataclass(frozen=True)
class OptimizationOutcome:
    result: OptimizationResult | None = None
    failure: ValidationOutcome | None = None


class OptimizationService:
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
        self._profile = profile

    def optimize(
        self,
        base: MissionState,
        *,
        seed: int,
        cap: int,
        robustness_samples: int,
        now: datetime,
    ) -> OptimizationOutcome:
        outcome = self._missions.validate(base, now)
        if outcome.analysis is None:
            return OptimizationOutcome(failure=outcome)
        scenario = self._templates.scenario_inputs(base.scenario_id)
        if scenario is None:
            raise LookupError(f"no template for scenario {base.scenario_id!r}")
        result = optimize(
            base,
            self._catalogs.catalog,
            scenario=scenario,
            seed=seed,
            cap=cap,
            engine_version=self._engine_version,
            now=now,
            profile=self._profile,
            robustness_samples=robustness_samples,
        )
        return OptimizationOutcome(result=result)

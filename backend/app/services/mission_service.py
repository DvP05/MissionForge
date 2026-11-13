"""Mission validation + analysis orchestration (no HTTP types here)."""

import re
from dataclasses import dataclass, field
from datetime import datetime

from app.domain.analysis.orchestrator import analyze_mission
from app.domain.mission.validation import validate_mission_state
from app.schemas.analysis import MissionAnalysis
from app.schemas.mission import MissionState, ValidationIssue
from app.services.catalog_service import CatalogService
from app.services.template_service import TemplateService

_ARCH_PATH = re.compile(r"^architecture\.(\w+)(?:\[(\d+)\])?$")


@dataclass(frozen=True)
class MissingComponent:
    path: str
    id: str


@dataclass(frozen=True)
class ValidationOutcome:
    """Exactly one of: analysis, missing_components, issues."""

    analysis: MissionAnalysis | None = None
    missing_components: tuple[MissingComponent, ...] = field(default_factory=tuple)
    issues: tuple[ValidationIssue, ...] = field(default_factory=tuple)


class MissionService:
    def __init__(
        self, catalogs: CatalogService, templates: TemplateService, engine_version: str
    ) -> None:
        self._catalogs = catalogs
        self._templates = templates
        self._engine_version = engine_version

    def _component_id(self, state: MissionState, path: str) -> str:
        match = _ARCH_PATH.match(path)
        if not match:
            return ""
        value = state.model_dump(by_alias=True)["architecture"].get(match.group(1))
        if match.group(2) is not None and isinstance(value, (list, tuple)):
            return str(value[int(match.group(2))])
        return str(value)

    def validate(self, state: MissionState, now: datetime) -> ValidationOutcome:
        issues = validate_mission_state(state, self._catalogs.catalog)
        unknown = [i for i in issues if i.code == "UNKNOWN_COMPONENT"]
        if unknown:
            return ValidationOutcome(
                missing_components=tuple(
                    MissingComponent(i.path, self._component_id(state, i.path)) for i in unknown
                )
            )
        if issues:
            return ValidationOutcome(issues=tuple(issues))
        scenario = self._templates.scenario_inputs(state.scenario_id)
        if scenario is None:  # unreachable for the Literal scenario ids; fail loudly, not silently
            raise LookupError(f"no template for scenario {state.scenario_id!r}")
        analysis = analyze_mission(
            state,
            self._catalogs.catalog,
            scenario=scenario,
            engine_version=self._engine_version,
            now=now,
        )
        return ValidationOutcome(analysis=analysis)

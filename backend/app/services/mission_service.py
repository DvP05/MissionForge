"""Mission validation + analysis orchestration (no HTTP types here)."""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from app.domain.analysis.orchestrator import analyze_mission
from app.domain.analysis.trade import compute_deltas
from app.domain.mission.validation import validate_mission_state
from app.schemas.analysis import MissionAnalysis
from app.schemas.mission import MissionState, ValidationIssue
from app.schemas.optimization import TradeAlternative, TradeStudyResult
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


@dataclass(frozen=True)
class DesignRef:
    """Which design of a trade study an outcome refers to (base has no index)."""

    role: Literal["base", "alternative"]
    index: int | None = None


@dataclass(frozen=True)
class TradeOutcome:
    """Either a result, or the first design that failed validation with its outcome."""

    result: TradeStudyResult | None = None
    failed_design: DesignRef | None = None
    failure: ValidationOutcome | None = None


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

    def trade_study(
        self,
        base: MissionState,
        alternatives: Sequence[MissionState],
        now: datetime,
    ) -> TradeOutcome:
        """Run the R22 validate flow on every design, then diff each alternative against base."""
        designs: list[tuple[DesignRef, MissionState]] = [(DesignRef("base"), base)]
        designs += [(DesignRef("alternative", i), alt) for i, alt in enumerate(alternatives)]
        analyses: list[MissionAnalysis] = []
        for ref, state in designs:
            outcome = self.validate(state, now)
            if outcome.analysis is None:
                return TradeOutcome(failed_design=ref, failure=outcome)
            analyses.append(outcome.analysis)
        base_analysis, *alt_analyses = analyses
        return TradeOutcome(
            result=TradeStudyResult(
                base_analysis=base_analysis,
                alternatives=[
                    TradeAlternative(analysis=a, deltas=compute_deltas(base_analysis, a))
                    for a in alt_analyses
                ],
            )
        )

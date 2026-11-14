"""Mission Analyst orchestration (Task 6.8). No HTTP types here."""

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.analyst import explain_constraint, recommend
from app.domain.architecture_graph import build_architecture_graph
from app.schemas.analyst import Recommendation
from app.schemas.mission import MissionState
from app.services.catalog_service import CatalogService
from app.services.mission_service import MissionService, ValidationOutcome
from app.services.template_service import TemplateService


@dataclass(frozen=True)
class AnalystResult:
    recommendations: list[Recommendation]
    explanations: dict[str, list[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class AnalystOutcome:
    result: AnalystResult | None = None
    failure: ValidationOutcome | None = None


class AnalystService:
    def __init__(
        self,
        missions: MissionService,
        catalogs: CatalogService,
        templates: TemplateService,
        engine_version: str,
    ) -> None:
        self._missions = missions
        self._catalogs = catalogs
        self._templates = templates
        self._engine_version = engine_version

    def recommend(self, state: MissionState, *, max_n: int, now: datetime) -> AnalystOutcome:
        outcome = self._missions.validate(state, now)
        if outcome.analysis is None:
            return AnalystOutcome(failure=outcome)
        scenario = self._templates.scenario_inputs(state.scenario_id)
        if scenario is None:
            raise LookupError(f"no template for scenario {state.scenario_id!r}")
        catalog = self._catalogs.catalog
        recs = recommend(
            state,
            outcome.analysis,
            catalog,
            scenario=scenario,
            engine_version=self._engine_version,
            now=now,
            max_n=max_n,
        )
        graph = build_architecture_graph(state, outcome.analysis, catalog)
        explanations = {
            c.id: explain_constraint(outcome.analysis, graph, c.id)
            for c in outcome.analysis.constraints
            if c.status in ("fail", "warning")
        }
        return AnalystOutcome(result=AnalystResult(recs, explanations))

"""Architecture graph + impact orchestration (Task 6.1). No HTTP types here."""

from dataclasses import dataclass
from datetime import datetime

from app.domain.architecture_graph import (
    MissionTraceRow,
    ScienceTraceRow,
    build_architecture_graph,
    build_traceability_matrices,
    trace_impact,
)
from app.schemas.mission import MissionState
from app.schemas.optimization import ArchitectureGraph, ImpactReport
from app.services.catalog_service import CatalogService
from app.services.mission_service import DesignRef, MissionService, ValidationOutcome


@dataclass(frozen=True)
class GraphResult:
    graph: ArchitectureGraph
    science_traceability: list[ScienceTraceRow]
    mission_traceability: list[MissionTraceRow]


@dataclass(frozen=True)
class GraphOutcome:
    """Either a result, or the validation failure that prevented it."""

    result: GraphResult | None = None
    failure: ValidationOutcome | None = None


@dataclass(frozen=True)
class ImpactOutcome:
    """Either an impact report (with the graph of the edited design), or a failure."""

    impact: ImpactReport | None = None
    graph: ArchitectureGraph | None = None
    failed_design: DesignRef | None = None
    failure: ValidationOutcome | None = None


class GraphService:
    def __init__(self, missions: MissionService, catalogs: CatalogService) -> None:
        self._missions = missions
        self._catalogs = catalogs

    def graph(self, state: MissionState, now: datetime) -> GraphOutcome:
        outcome = self._missions.validate(state, now)
        if outcome.analysis is None:
            return GraphOutcome(failure=outcome)
        graph = build_architecture_graph(state, outcome.analysis, self._catalogs.catalog)
        stm, mtm = build_traceability_matrices(graph)
        return GraphOutcome(result=GraphResult(graph, stm, mtm))

    def impact(self, before: MissionState, after: MissionState, now: datetime) -> ImpactOutcome:
        """Analyse both revisions and explain what the edit changed. Nothing is mutated."""
        before_outcome = self._missions.validate(before, now)
        if before_outcome.analysis is None:
            return ImpactOutcome(failed_design=DesignRef("base"), failure=before_outcome)
        after_outcome = self._missions.validate(after, now)
        if after_outcome.analysis is None:
            return ImpactOutcome(failed_design=DesignRef("alternative", 0), failure=after_outcome)
        catalog = self._catalogs.catalog
        before_graph = build_architecture_graph(before, before_outcome.analysis, catalog)
        graph = build_architecture_graph(after, after_outcome.analysis, catalog)
        impact = trace_impact(
            before_outcome.analysis, after_outcome.analysis, graph, before_graph=before_graph
        )
        return ImpactOutcome(impact=impact, graph=graph)

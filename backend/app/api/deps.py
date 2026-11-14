"""FastAPI dependencies: services live on app.state (built once at startup)."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

from fastapi import Request

from app.services.analyst_service import AnalystService
from app.services.catalog_service import CatalogService
from app.services.graph_service import GraphService
from app.services.mission_service import MissionService
from app.services.optimization_service import OptimizationService
from app.services.robustness_service import RobustnessService
from app.services.schedule_service import ScheduleService
from app.services.science_service import ScienceService
from app.services.simulation_service import SimulationService
from app.services.template_service import TemplateService, new_mission_id

Clock = Callable[[], datetime]


def get_catalog_service(request: Request) -> CatalogService:
    return cast(CatalogService, request.app.state.catalog_service)


def get_template_service(request: Request) -> TemplateService:
    return cast(TemplateService, request.app.state.template_service)


def get_mission_service(request: Request) -> MissionService:
    return cast(MissionService, request.app.state.mission_service)


def get_simulation_service(request: Request) -> SimulationService:
    return cast(SimulationService, request.app.state.simulation_service)


def get_graph_service(request: Request) -> GraphService:
    return cast(GraphService, request.app.state.graph_service)


def get_robustness_service(request: Request) -> RobustnessService:
    return cast(RobustnessService, request.app.state.robustness_service)


def get_optimization_service(request: Request) -> OptimizationService:
    return cast(OptimizationService, request.app.state.optimization_service)


def get_analyst_service(request: Request) -> AnalystService:
    return cast(AnalystService, request.app.state.analyst_service)


def get_science_service(request: Request) -> ScienceService:
    return cast(ScienceService, request.app.state.science_service)


def get_schedule_service(request: Request) -> ScheduleService:
    return cast(ScheduleService, request.app.state.schedule_service)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def get_clock() -> Clock:
    return _utc_now


def get_mission_id_factory() -> Callable[[], str]:
    return new_mission_id

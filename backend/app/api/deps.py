"""FastAPI dependencies: services live on app.state (built once at startup)."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

from fastapi import Request

from app.services.catalog_service import CatalogService
from app.services.mission_service import MissionService
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


def _utc_now() -> datetime:
    return datetime.now(UTC)


def get_clock() -> Clock:
    return _utc_now


def get_mission_id_factory() -> Callable[[], str]:
    return new_mission_id

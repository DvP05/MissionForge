import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_error_handlers
from app.api.middleware import BodySizeLimitMiddleware
from app.api.routes import (
    analyst,
    catalog,
    graph,
    health,
    health_monitor,
    missions,
    optimization,
    robustness,
    schedule,
    science,
    templates,
)
from app.config import DEFAULT_SCENARIOS_DIR, get_settings
from app.domain.analysis.orchestrator import ENGINE_VERSION
from app.domain.simulation.anomalies import load_event_sets
from app.services.analyst_service import AnalystService
from app.services.catalog_service import CatalogService
from app.services.graph_service import GraphService
from app.services.health_monitor_service import HealthMonitorService
from app.services.mission_service import MissionService
from app.services.optimization_service import OptimizationService
from app.services.research_evidence_service import ResearchEvidenceService
from app.services.robustness_service import RobustnessService, load_profile
from app.services.schedule_service import ScheduleService
from app.services.science_service import ScienceService, load_science_models
from app.services.simulation_service import SimulationService
from app.services.template_service import TemplateService


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)

    # Services own the I/O: the catalogue and templates are loaded once, here.
    catalogs = CatalogService.from_directory()
    template_service = TemplateService.from_directory()
    app.state.catalog_service = catalogs
    app.state.template_service = template_service
    mission_service = MissionService(catalogs, template_service, ENGINE_VERSION)
    app.state.mission_service = mission_service
    science_models = load_science_models()
    app.state.simulation_service = SimulationService(
        mission_service,
        catalogs.catalog,
        template_service,
        load_event_sets(DEFAULT_SCENARIOS_DIR),
        engine_version=ENGINE_VERSION,
        app_version=settings.app_version,
        science_models=science_models,
    )

    # Phase 6 research differentiators (graph, arena, robustness, analyst, science, schedule).
    profile = load_profile()
    app.state.graph_service = GraphService(mission_service, catalogs)
    app.state.robustness_service = RobustnessService(
        mission_service, catalogs, template_service, ENGINE_VERSION, profile
    )
    app.state.optimization_service = OptimizationService(
        mission_service, catalogs, template_service, ENGINE_VERSION, profile
    )
    app.state.analyst_service = AnalystService(
        mission_service, catalogs, template_service, ENGINE_VERSION
    )
    app.state.science_service = ScienceService(science_models)
    app.state.schedule_service = ScheduleService(mission_service, catalogs)
    app.state.health_monitor_service = HealthMonitorService(app.state.simulation_service)
    # Phase 4 <-> 6 join: Evidence Passport v2 recomputes Phase 6 evidence for a run.
    app.state.research_evidence_service = ResearchEvidenceService(
        app.state.graph_service,
        app.state.optimization_service,
        app.state.robustness_service,
        app.state.schedule_service,
        app.state.health_monitor_service,
    )

    # Added innermost-first: size limit, then CORS, then the request id (outermost).
    app.add_middleware(
        BodySizeLimitMiddleware,
        max_bytes=settings.max_request_bytes,
        path_limits={
            "/api/mission/import": settings.max_import_bytes,
        },
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    register_error_handlers(app, settings.cors_origins)

    app.include_router(health.router, prefix="/api")
    app.include_router(catalog.router, prefix="/api")
    app.include_router(templates.router, prefix="/api")
    app.include_router(missions.router, prefix="/api")
    app.include_router(graph.router, prefix="/api")
    app.include_router(robustness.router, prefix="/api")
    app.include_router(optimization.router, prefix="/api")
    app.include_router(analyst.router, prefix="/api")
    app.include_router(science.router, prefix="/api")
    app.include_router(schedule.router, prefix="/api")
    app.include_router(health_monitor.router, prefix="/api")
    return app


app = create_app()

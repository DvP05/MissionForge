import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_error_handlers
from app.api.middleware import BodySizeLimitMiddleware
from app.api.routes import catalog, health, health_monitor, missions, space_data, templates
from app.config import DEFAULT_JPL_SNAPSHOT, DEFAULT_SCENARIOS_DIR, get_settings
from app.domain.simulation.anomalies import load_event_sets
from app.integrations.jpl.client import JplMDesignClient
from app.services.catalog_service import CatalogService
from app.services.mission_service import MissionService
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
    mission_service = MissionService(catalogs, template_service, settings.engine_version)
    app.state.mission_service = mission_service
    app.state.simulation_service = SimulationService(
        mission_service,
        catalogs.catalog,
        template_service,
        load_event_sets(DEFAULT_SCENARIOS_DIR),
        engine_version=settings.engine_version,
        app_version=settings.app_version,
    )
    app.state.jpl_client = JplMDesignClient(settings, snapshot_path=DEFAULT_JPL_SNAPSHOT)

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
    app.include_router(health_monitor.router, prefix="/api")
    app.include_router(space_data.router, prefix="/api")
    return app


app = create_app()

import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import health
from app.config import get_settings
from app.schemas.api import ApiError, ApiMeta, ApiResult

logger = logging.getLogger("missionforge")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)

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

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", exc_info=exc)
        request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
        body = ApiResult[None](
            ok=False,
            error=ApiError(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred.",
                retryable=False,
            ),
            meta=ApiMeta(request_id=request_id),
        )
        return JSONResponse(
            status_code=500,
            content=body.model_dump(mode="json", by_alias=True),
            headers={"X-Request-ID": request_id},
        )

    app.include_router(health.router, prefix="/api")
    return app


app = create_app()

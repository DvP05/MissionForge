"""Every error leaves the API as an ApiResult envelope (architecture 11.1, 13).

Handlers never echo exception text, tracebacks or request input; 4xx messages are fixed
strings, field paths come from the validation locations only.
"""

import logging
import uuid
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.api import ApiError, ApiMeta, ApiResult

logger = logging.getLogger("missionforge")

VALIDATION_ERROR = "VALIDATION_ERROR"
CATALOG_ITEM_NOT_FOUND = "CATALOG_ITEM_NOT_FOUND"
PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
INTERNAL_ERROR = "INTERNAL_ERROR"

_STATUS_CODES: dict[int, str] = {
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    413: PAYLOAD_TOO_LARGE,
}
_STATUS_MESSAGES: dict[int, str] = {
    404: "The requested resource was not found.",
    405: "This method is not allowed for the requested resource.",
    413: "The request body is too large.",
}


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", None) or uuid.uuid4())


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    retryable: bool = False,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    body = ApiResult[None](
        ok=False,
        error=ApiError(code=code, message=message, retryable=retryable, details=details),
        meta=ApiMeta(request_id=request_id),
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json", by_alias=True),
        headers={**(headers or {}), "X-Request-ID": request_id},
    )


def _loc_path(loc: tuple[Any, ...]) -> str:
    out = ""
    for part in loc:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += f".{part}" if out else str(part)
    return out


def validation_fields(exc: RequestValidationError) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    for err in exc.errors():
        loc = tuple(err.get("loc", ()))
        if loc and loc[0] == "body":
            loc = loc[1:]  # the body itself is the request root
        fields.append(
            {"path": _loc_path(loc), "message": str(err.get("msg", "invalid")), "type": err["type"]}
        )
    return fields


def validation_fields_from_pydantic(exc: ValidationError) -> list[dict[str, str]]:
    """Field issues from a model_validate failure (paths and messages only, never input values)."""
    fields = [
        {
            "path": _loc_path(tuple(err.get("loc", ()))),
            "message": str(err.get("msg", "invalid")),
            "type": err["type"],
        }
        for err in exc.errors(include_input=False, include_url=False)
    ]
    return fields[:50]


def register_error_handlers(app: FastAPI, cors_origins: list[str]) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(
            request,
            422,
            VALIDATION_ERROR,
            "The request is not valid.",
            details={"fields": validation_fields(exc)},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code)
        if code is None:
            code = "CLIENT_ERROR" if exc.status_code < 500 else INTERNAL_ERROR
        message = _STATUS_MESSAGES.get(exc.status_code) or HTTPStatus(exc.status_code).phrase
        return error_response(
            request, exc.status_code, code, message, headers=dict(exc.headers or {})
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # ServerErrorMiddleware runs outside CORSMiddleware, so CORS headers are added here.
        logger.exception("Unhandled error", exc_info=exc)
        origin = request.headers.get("origin")
        cors: dict[str, str] = {}
        if origin is not None and origin in cors_origins:
            cors = {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Expose-Headers": "X-Request-ID",
                "Vary": "Origin",
            }
        return error_response(
            request, 500, INTERNAL_ERROR, "An unexpected error occurred.", headers=cors
        )

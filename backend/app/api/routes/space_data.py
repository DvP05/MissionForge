"""JPL-backed space data routes (Task 5.3, architecture 10.3, decision D7).

GET /api/space-data/neo-accessible   (JPL mode A)
GET /api/space-data/neo/{designation} (JPL mode Q)

Only normalised fields leave the server (no raw JPL keys); ``meta.sourceStatus`` says
whether the data is live, cached or from the bundled offline snapshot.
"""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.api.errors import error_response
from app.domain.errors import DomainValidationError
from app.integrations.jpl.repository import JplRepository
from app.schemas.api import ApiMeta, ApiResult
from app.schemas.space_data import NeoAccessibleData, NeoDetailData

router = APIRouter()

_MESSAGES = {
    "VALIDATION_ERROR": "The search settings are not allowed.",
    "JPL_UNAVAILABLE": "JPL data is unavailable and no offline data covers this request.",
}


def get_jpl_repository(request: Request) -> JplRepository:
    return cast(JplRepository, request.app.state.jpl_repository)


def _error(request: Request, exc: DomainValidationError) -> JSONResponse:
    if exc.code == "VALIDATION_ERROR":
        return error_response(
            request, 422, exc.code, _MESSAGES[exc.code], details={"field": exc.field}
        )
    return error_response(
        request, 503, "JPL_UNAVAILABLE", _MESSAGES["JPL_UNAVAILABLE"], retryable=True
    )


@router.get("/space-data/neo-accessible", response_model=ApiResult[NeoAccessibleData])
async def neo_accessible(
    request: Request,
    repo: Annotated[JplRepository, Depends(get_jpl_repository)],
    years: Annotated[str, Query(max_length=40, pattern=r"^\d{4}(,\d{4}){0,4}$")] = "2031",
    criterion: Annotated[int, Query()] = 1,
    limit: Annotated[int, Query()] = 20,
) -> ApiResult[NeoAccessibleData] | JSONResponse:
    try:
        data = await repo.neo_accessible([int(y) for y in years.split(",")], criterion, limit)
    except DomainValidationError as exc:
        return _error(request, exc)
    return ApiResult[NeoAccessibleData](
        ok=True,
        data=data,
        meta=ApiMeta(request_id=request.state.request_id, source_status=data.source.status),
    )


@router.get("/space-data/neo/{designation}", response_model=ApiResult[NeoDetailData])
async def neo_detail(
    designation: str,
    request: Request,
    repo: Annotated[JplRepository, Depends(get_jpl_repository)],
) -> ApiResult[NeoDetailData] | JSONResponse:
    try:
        data = await repo.neo_detail(designation)
    except DomainValidationError as exc:
        return _error(request, exc)
    return ApiResult[NeoDetailData](
        ok=True,
        data=data,
        meta=ApiMeta(request_id=request.state.request_id, source_status=data.source.status),
    )

from fastapi import APIRouter, Request

from app.integrations.jpl.client import SpaceDataResponse
from app.schemas.api import ApiMeta, ApiResult

router = APIRouter(prefix="/space-data")


@router.get("/neo-accessible", response_model=ApiResult[SpaceDataResponse])
def neo_accessible(request: Request) -> ApiResult[SpaceDataResponse]:
    client = request.app.state.jpl_client
    data = client.get("SCENARIO-NEO-A")
    return ApiResult[SpaceDataResponse](
        ok=True,
        data=data,
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.get("/neo/{designation}", response_model=ApiResult[SpaceDataResponse])
def neo_by_designation(
    designation: str,
    request: Request,
) -> ApiResult[SpaceDataResponse]:
    client = request.app.state.jpl_client
    data = client.get(designation)
    return ApiResult[SpaceDataResponse](
        ok=True,
        data=data,
        meta=ApiMeta(request_id=request.state.request_id),
    )

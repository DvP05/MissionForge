from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.api.deps import Clock, get_clock, get_mission_service
from app.api.errors import CATALOG_ITEM_NOT_FOUND, VALIDATION_ERROR, error_response
from app.config import Settings, get_settings
from app.schemas.analysis import MissionAnalysis
from app.schemas.api import ApiMeta, ApiResult, ContractModel
from app.schemas.mission import MissionState
from app.services.mission_service import MissionService


class ValidateRequest(ContractModel):
    mission_state: MissionState


class ValidateData(ContractModel):
    analysis: MissionAnalysis


router = APIRouter()


@router.post("/mission/validate", response_model=ApiResult[ValidateData])
def validate_mission(
    body: ValidateRequest,
    request: Request,
    service: Annotated[MissionService, Depends(get_mission_service)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApiResult[ValidateData] | JSONResponse:
    outcome = service.validate(body.mission_state, clock())
    if outcome.missing_components:
        return error_response(
            request,
            422,
            CATALOG_ITEM_NOT_FOUND,
            "The design references catalogue components that do not exist.",
            details={
                "catalogVersion": settings.catalog_version,
                "items": [{"path": m.path, "id": m.id} for m in outcome.missing_components],
            },
        )
    if outcome.issues:
        return error_response(
            request,
            422,
            VALIDATION_ERROR,
            "The mission state is inconsistent.",
            details={"issues": [i.model_dump(by_alias=True) for i in outcome.issues]},
        )
    if outcome.analysis is None:
        raise RuntimeError("mission service returned no outcome")
    return ApiResult[ValidateData](
        ok=True,
        data=ValidateData(analysis=outcome.analysis),
        meta=ApiMeta(request_id=request.state.request_id),
    )

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import Field

from app.api.deps import Clock, get_clock, get_mission_service
from app.api.errors import CATALOG_ITEM_NOT_FOUND, VALIDATION_ERROR, error_response
from app.config import Settings, get_settings
from app.schemas.analysis import MissionAnalysis
from app.schemas.api import ApiMeta, ApiResult, ContractModel
from app.schemas.mission import MissionState
from app.schemas.optimization import TradeStudyResult
from app.services.mission_service import DesignRef, MissionService, ValidationOutcome

MAX_TRADE_ALTERNATIVES = 3


class ValidateRequest(ContractModel):
    mission_state: MissionState


class ValidateData(ContractModel):
    analysis: MissionAnalysis


class TradeStudyRequest(ContractModel):
    base_mission_state: MissionState
    alternatives: Annotated[
        list[MissionState], Field(min_length=1, max_length=MAX_TRADE_ALTERNATIVES)
    ]


router = APIRouter()


def _failure_response(
    request: Request,
    settings: Settings,
    outcome: ValidationOutcome,
    design: DesignRef | None = None,
) -> JSONResponse:
    """Maps a failed validation outcome to the error envelope (R22); `design` tags trade studies."""
    extra = {"design": {"role": design.role, "index": design.index}} if design is not None else {}
    if outcome.missing_components:
        return error_response(
            request,
            422,
            CATALOG_ITEM_NOT_FOUND,
            "The design references catalogue components that do not exist.",
            details={
                "catalogVersion": settings.catalog_version,
                "items": [{"path": m.path, "id": m.id} for m in outcome.missing_components],
                **extra,
            },
        )
    return error_response(
        request,
        422,
        VALIDATION_ERROR,
        "The mission state is inconsistent.",
        details={"issues": [i.model_dump(by_alias=True) for i in outcome.issues], **extra},
    )


@router.post("/mission/validate", response_model=ApiResult[ValidateData])
def validate_mission(
    body: ValidateRequest,
    request: Request,
    service: Annotated[MissionService, Depends(get_mission_service)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApiResult[ValidateData] | JSONResponse:
    outcome = service.validate(body.mission_state, clock())
    if outcome.analysis is None:
        return _failure_response(request, settings, outcome)
    return ApiResult[ValidateData](
        ok=True,
        data=ValidateData(analysis=outcome.analysis),
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.post("/mission/trade-study", response_model=ApiResult[TradeStudyResult])
def trade_study(
    body: TradeStudyRequest,
    request: Request,
    service: Annotated[MissionService, Depends(get_mission_service)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApiResult[TradeStudyResult] | JSONResponse:
    """Compare 1-3 alternatives against a base design (architecture 11.2). Nothing is mutated."""
    outcome = service.trade_study(body.base_mission_state, body.alternatives, clock())
    if outcome.result is None:
        if outcome.failure is None or outcome.failed_design is None:
            raise RuntimeError("trade study returned neither a result nor a failure")
        return _failure_response(request, settings, outcome.failure, outcome.failed_design)
    return ApiResult[TradeStudyResult](
        ok=True, data=outcome.result, meta=ApiMeta(request_id=request.state.request_id)
    )

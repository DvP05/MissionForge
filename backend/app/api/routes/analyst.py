"""Mission Analyst route (Task 6.8): POST /api/mission/recommend."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import Field, StrictInt

from app.api.deps import Clock, get_analyst_service, get_clock
from app.api.routes.missions import _failure_response
from app.config import Settings, get_settings
from app.domain.analyst import MAX_RECOMMENDATIONS
from app.schemas.analyst import Recommendation
from app.schemas.api import ApiMeta, ApiResult, ContractModel
from app.schemas.mission import MissionState
from app.services.analyst_service import AnalystService

router = APIRouter()


class RecommendRequest(ContractModel):
    mission_state: MissionState
    max_n: StrictInt = Field(default=3, ge=1, le=MAX_RECOMMENDATIONS)


class RecommendData(ContractModel):
    mission_id: str
    design_revision: StrictInt
    recommendations: list[Recommendation]
    # constraint id -> plain-language "because" lines, for every failing/watch constraint
    explanations: dict[str, list[str]]


@router.post("/mission/recommend", response_model=ApiResult[RecommendData])
def mission_recommend(
    body: RecommendRequest,
    request: Request,
    service: Annotated[AnalystService, Depends(get_analyst_service)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApiResult[RecommendData] | JSONResponse:
    """Deterministic one-step improvements computed by the engine (architecture 19.8)."""
    outcome = service.recommend(body.mission_state, max_n=body.max_n, now=clock())
    if outcome.result is None:
        if outcome.failure is None:
            raise RuntimeError("recommend returned neither a result nor a failure")
        return _failure_response(request, settings, outcome.failure)
    return ApiResult[RecommendData](
        ok=True,
        data=RecommendData(
            mission_id=body.mission_state.mission_id,
            design_revision=body.mission_state.design_revision,
            recommendations=outcome.result.recommendations,
            explanations=outcome.result.explanations,
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )

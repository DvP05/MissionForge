from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.deps import Clock, get_clock, get_mission_id_factory, get_template_service
from app.schemas.api import ApiMeta, ApiResult
from app.schemas.mission import MissionState
from app.schemas.templates import ScenarioTemplate
from app.services.template_service import TemplateService

router = APIRouter()

DEFAULT_SEED = 42


@router.get("/templates", response_model=ApiResult[list[ScenarioTemplate]])
def list_templates(
    request: Request, service: Annotated[TemplateService, Depends(get_template_service)]
) -> ApiResult[list[ScenarioTemplate]]:
    return ApiResult[list[ScenarioTemplate]](
        ok=True, data=service.list(), meta=ApiMeta(request_id=request.state.request_id)
    )


@router.get("/templates/{scenario_id}/default-mission", response_model=ApiResult[MissionState])
def default_mission(
    scenario_id: str,
    request: Request,
    service: Annotated[TemplateService, Depends(get_template_service)],
    clock: Annotated[Clock, Depends(get_clock)],
    new_id: Annotated[Callable[[], str], Depends(get_mission_id_factory)],
    seed: Annotated[int, Query(ge=0, le=2**31 - 1)] = DEFAULT_SEED,
) -> ApiResult[MissionState]:
    if service.get(scenario_id) is None:
        raise HTTPException(status_code=404)
    state = service.default_mission(scenario_id, seed=seed, mission_id=new_id(), now=clock())
    return ApiResult[MissionState](
        ok=True, data=state, meta=ApiMeta(request_id=request.state.request_id)
    )

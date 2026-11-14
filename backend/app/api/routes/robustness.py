"""Robustness lab route (Task 6.3): POST /api/mission/robustness."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import Field, StrictInt

from app.api.deps import Clock, get_clock, get_robustness_service
from app.api.errors import error_response
from app.api.routes.missions import _failure_response
from app.config import Settings, get_settings
from app.domain.uncertainty import MAX_SAMPLES
from app.schemas.api import ApiMeta, ApiResult, ContractModel
from app.schemas.mission import MissionState
from app.schemas.uncertainty import RobustnessResult
from app.services.robustness_service import RobustnessService

DEFAULT_SAMPLES = 250
SIMULATION_LIMIT_EXCEEDED = "SIMULATION_LIMIT_EXCEEDED"

router = APIRouter()


class RobustnessRequest(ContractModel):
    mission_state: MissionState
    samples: StrictInt = Field(default=DEFAULT_SAMPLES, ge=1)
    seed: StrictInt | None = None  # defaults to the mission's random_seed


class RobustnessData(ContractModel):
    mission_id: str
    design_revision: StrictInt
    result: RobustnessResult


@router.post("/mission/robustness", response_model=ApiResult[RobustnessData])
def mission_robustness(
    body: RobustnessRequest,
    request: Request,
    service: Annotated[RobustnessService, Depends(get_robustness_service)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApiResult[RobustnessData] | JSONResponse:
    """Seeded Monte Carlo robustness proxy (architecture 19.3); default 250 samples."""
    if body.samples > MAX_SAMPLES:
        return error_response(
            request,
            422,
            SIMULATION_LIMIT_EXCEEDED,
            f"At most {MAX_SAMPLES} robustness samples can be run per request.",
            details={"maxSamples": MAX_SAMPLES, "requested": body.samples},
        )
    seed = body.seed if body.seed is not None else body.mission_state.random_seed
    outcome = service.run(body.mission_state, samples=body.samples, seed=seed, now=clock())
    if outcome.result is None:
        if outcome.failure is None:
            raise RuntimeError("robustness returned neither a result nor a failure")
        return _failure_response(request, settings, outcome.failure)
    return ApiResult[RobustnessData](
        ok=True,
        data=RobustnessData(
            mission_id=body.mission_state.mission_id,
            design_revision=body.mission_state.design_revision,
            result=outcome.result,
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )

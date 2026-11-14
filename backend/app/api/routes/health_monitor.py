"""Predictive health monitor route (Task 6.7): POST /api/mission/health.

Takes a recorded run (re-validated by the schema) and recomputes, server-side, the nominal
model and the EWMA-residual findings; nothing from the client is trusted as a result.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.api.deps import Clock, get_clock, get_health_monitor_service
from app.api.routes.missions import _failure_response
from app.config import Settings, get_settings
from app.schemas.api import ApiMeta, ApiResult, ContractModel
from app.schemas.health import HealthReport
from app.schemas.simulation import MissionRun
from app.services.health_monitor_service import HealthMonitorService

router = APIRouter()


class HealthRequest(ContractModel):
    run: MissionRun


@router.post("/mission/health", response_model=ApiResult[HealthReport])
def monitor_health(
    body: HealthRequest,
    request: Request,
    service: Annotated[HealthMonitorService, Depends(get_health_monitor_service)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApiResult[HealthReport] | JSONResponse:
    outcome = service.monitor(body.run, clock())
    if outcome.report is None:
        if outcome.failure is None:
            raise RuntimeError("health monitor returned neither a report nor a failure")
        return _failure_response(request, settings, outcome.failure)
    return ApiResult[HealthReport](
        ok=True, data=outcome.report, meta=ApiMeta(request_id=request.state.request_id)
    )

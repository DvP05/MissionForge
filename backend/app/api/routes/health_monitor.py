from fastapi import APIRouter, Request
from pydantic import Field

from app.domain.health_monitor.detector import detect_anomalies
from app.schemas.api import ApiMeta, ApiResult, ContractModel
from app.schemas.health import Anomaly, DetectorConfig
from app.schemas.simulation import TelemetrySample

router = APIRouter(prefix="/mission")


class HealthMonitorRequest(ContractModel):
    telemetry: list[TelemetrySample] = Field(max_length=10000)
    config: DetectorConfig


class HealthMonitorData(ContractModel):
    anomalies: list[Anomaly]
    disclaimer: str


@router.post("/health-monitor", response_model=ApiResult[HealthMonitorData])
def health_monitor(
    body: HealthMonitorRequest,
    request: Request,
) -> ApiResult[HealthMonitorData]:
    anomalies = detect_anomalies(body.telemetry, body.config)
    return ApiResult[HealthMonitorData](
        ok=True,
        data=HealthMonitorData(
            anomalies=anomalies,
            disclaimer="Educational transparent detector; not flight-qualified fault diagnosis.",
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )

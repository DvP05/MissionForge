from typing import Literal

from fastapi import APIRouter, Request

from app.config import get_settings
from app.domain.analysis.orchestrator import ENGINE_VERSION
from app.schemas.api import ApiMeta, ApiResult, ContractModel


class JplAdapterStatus(ContractModel):
    status: Literal["live", "cached", "demo", "unknown"]


class HealthData(ContractModel):
    app_name: str
    app_version: str
    engine_version: str
    catalog_version: str
    schema_version: str
    jpl_adapter: JplAdapterStatus


router = APIRouter()


def _jpl_status(request: Request) -> Literal["live", "cached", "demo", "unknown"]:
    repo = getattr(request.app.state, "jpl_repository", None)
    return repo.status_label() if repo is not None else "unknown"


@router.get("/health", response_model=ApiResult[HealthData])
def health(request: Request) -> ApiResult[HealthData]:
    settings = get_settings()
    data = HealthData(
        app_name=settings.app_name,
        app_version=settings.app_version,
        engine_version=ENGINE_VERSION,  # R40: single source
        catalog_version=request.app.state.catalog_service.version,
        schema_version=settings.mission_schema_version,
        jpl_adapter=JplAdapterStatus(status=_jpl_status(request)),
    )
    return ApiResult[HealthData](
        ok=True, data=data, meta=ApiMeta(request_id=request.state.request_id)
    )

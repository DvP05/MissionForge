from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_catalog_service
from app.schemas.api import ApiMeta, ApiResult, ContractModel
from app.schemas.catalog import CatalogComponent, ComponentCategory
from app.schemas.units import Fidelity
from app.services.catalog_service import CatalogService


class CatalogGroup(ContractModel):
    category: ComponentCategory
    components: list[CatalogComponent]


class CatalogSource(ContractModel):
    source_name: str
    source_url: str | None = None
    source_version: str | None = None
    fidelity: Fidelity
    component_count: int


class CatalogData(ContractModel):
    catalog_version: str
    groups: list[CatalogGroup]
    sources: list[CatalogSource]


router = APIRouter()


@router.get("/catalog", response_model=ApiResult[CatalogData])
def get_catalog(
    request: Request, service: Annotated[CatalogService, Depends(get_catalog_service)]
) -> ApiResult[CatalogData]:
    data = CatalogData(
        catalog_version=service.version,
        groups=[
            CatalogGroup(category=components[0].category, components=components)
            for _, components in service.groups()
        ],
        sources=[
            CatalogSource(
                source_name=s.source_name,
                source_url=s.source_url,
                source_version=s.source_version,
                fidelity=s.fidelity,
                component_count=s.component_count,
            )
            for s in service.sources()
        ],
    )
    return ApiResult[CatalogData](
        ok=True, data=data, meta=ApiMeta(request_id=request.state.request_id)
    )

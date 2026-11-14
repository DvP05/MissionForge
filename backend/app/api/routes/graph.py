"""Architecture graph routes (Task 6.1): POST /api/mission/graph and /api/mission/impact.

Kept in their own module (not missions.py) so parallel Phase 6 work does not collide.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import StrictBool, StrictInt

from app.api.deps import Clock, get_clock, get_graph_service
from app.api.routes.missions import _failure_response
from app.config import Settings, get_settings
from app.schemas.api import ApiMeta, ApiResult, ContractModel
from app.schemas.mission import MissionState
from app.schemas.optimization import ArchitectureGraph, ImpactReport
from app.services.graph_service import GraphService

router = APIRouter()


class GraphRequest(ContractModel):
    mission_state: MissionState


class ScienceTraceRowOut(ContractModel):
    objective_id: str
    objective_title: str
    requirement_id: str
    requirement_description: str
    capability: str
    required: StrictBool
    instrument_ids: list[str]
    observation_count: StrictInt
    status: str


class MissionTraceRowOut(ContractModel):
    instrument_id: str
    instrument_name: str
    requirement_ids: list[str]
    subsystem_ids: list[str]
    observation_count: StrictInt


class GraphData(ContractModel):
    mission_id: str
    design_revision: StrictInt
    graph: ArchitectureGraph
    science_traceability: list[ScienceTraceRowOut]
    mission_traceability: list[MissionTraceRowOut]


class ImpactRequest(ContractModel):
    before_mission_state: MissionState
    after_mission_state: MissionState


class ImpactData(ContractModel):
    before_revision: StrictInt
    after_revision: StrictInt
    impact: ImpactReport
    graph: ArchitectureGraph


@router.post("/mission/graph", response_model=ApiResult[GraphData])
def mission_graph(
    body: GraphRequest,
    request: Request,
    service: Annotated[GraphService, Depends(get_graph_service)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApiResult[GraphData] | JSONResponse:
    """Dependency graph plus STM/MTM tables for one design revision (architecture 19.1)."""
    outcome = service.graph(body.mission_state, clock())
    if outcome.result is None:
        if outcome.failure is None:
            raise RuntimeError("graph returned neither a result nor a failure")
        return _failure_response(request, settings, outcome.failure)
    r = outcome.result
    data = GraphData(
        mission_id=body.mission_state.mission_id,
        design_revision=body.mission_state.design_revision,
        graph=r.graph,
        science_traceability=[
            ScienceTraceRowOut(
                objective_id=row.objective_id,
                objective_title=row.objective_title,
                requirement_id=row.requirement_id,
                requirement_description=row.requirement_description,
                capability=row.capability,
                required=row.required,
                instrument_ids=list(row.instrument_ids),
                observation_count=row.observation_count,
                status=row.status,
            )
            for row in r.science_traceability
        ],
        mission_traceability=[
            MissionTraceRowOut(
                instrument_id=row.instrument_id,
                instrument_name=row.instrument_name,
                requirement_ids=list(row.requirement_ids),
                subsystem_ids=list(row.subsystem_ids),
                observation_count=row.observation_count,
            )
            for row in r.mission_traceability
        ],
    )
    return ApiResult[GraphData](
        ok=True, data=data, meta=ApiMeta(request_id=request.state.request_id)
    )


@router.post("/mission/impact", response_model=ApiResult[ImpactData])
def mission_impact(
    body: ImpactRequest,
    request: Request,
    service: Annotated[GraphService, Depends(get_graph_service)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApiResult[ImpactData] | JSONResponse:
    """What one edit changed: metrics, constraints and science objectives (19.1 behaviour 7)."""
    outcome = service.impact(body.before_mission_state, body.after_mission_state, clock())
    if outcome.impact is None or outcome.graph is None:
        if outcome.failure is None or outcome.failed_design is None:
            raise RuntimeError("impact returned neither a result nor a failure")
        return _failure_response(request, settings, outcome.failure, outcome.failed_design)
    return ApiResult[ImpactData](
        ok=True,
        data=ImpactData(
            before_revision=body.before_mission_state.design_revision,
            after_revision=body.after_mission_state.design_revision,
            impact=outcome.impact,
            graph=outcome.graph,
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )

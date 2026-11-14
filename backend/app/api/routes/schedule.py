"""Science/downlink scheduler route (Task 6.6): POST /api/mission/schedule."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import StrictBool, StrictInt

from app.api.deps import Clock, get_clock, get_schedule_service
from app.api.routes.missions import _failure_response
from app.config import Settings, get_settings
from app.schemas.api import ApiMeta, ApiResult, ContractModel
from app.schemas.mission import MissionState
from app.schemas.operations import ContactWindow, MissionSchedule, ObservationOpportunity
from app.schemas.units import FiniteFloat
from app.services.schedule_service import ScheduleService

ALGORITHM_NOTE = (
    "Greedy heuristic (highest science first, then earliest), not an optimal schedule. "
    "Data is counted on board when an observation ends; a contact returns at most its "
    "capacity and only data already on board."
)

router = APIRouter()


class ScheduleRequest(ContractModel):
    mission_state: MissionState
    accept_data_loss: StrictBool = False


class ScheduleData(ContractModel):
    mission_id: str
    design_revision: StrictInt
    opportunities: list[ObservationOpportunity]
    contacts: list[ContactWindow]
    measurement_of: dict[str, str]
    buffer_capacity_bits: FiniteFloat
    max_energy_per_observation_joules: FiniteFloat
    schedule: MissionSchedule
    algorithm: str


@router.post("/mission/schedule", response_model=ApiResult[ScheduleData])
def mission_schedule(
    body: ScheduleRequest,
    request: Request,
    service: Annotated[ScheduleService, Depends(get_schedule_service)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApiResult[ScheduleData] | JSONResponse:
    """Which planned observations fit storage, energy, pointing and contacts (19.6)."""
    outcome = service.schedule(
        body.mission_state, accept_data_loss=body.accept_data_loss, now=clock()
    )
    if outcome.result is None:
        if outcome.failure is None:
            raise RuntimeError("schedule returned neither a result nor a failure")
        return _failure_response(request, settings, outcome.failure)
    r = outcome.result
    return ApiResult[ScheduleData](
        ok=True,
        data=ScheduleData(
            mission_id=body.mission_state.mission_id,
            design_revision=body.mission_state.design_revision,
            opportunities=r.inputs.opportunities,
            contacts=r.inputs.contacts,
            measurement_of=r.inputs.measurement_of,
            buffer_capacity_bits=r.inputs.resources.buffer_capacity_bits,
            max_energy_per_observation_joules=r.inputs.resources.max_energy_per_observation_joules,
            schedule=r.schedule,
            algorithm=ALGORITHM_NOTE,
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )

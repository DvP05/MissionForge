"""Science/downlink scheduling orchestration (Task 6.6). No HTTP types here."""

from dataclasses import dataclass
from datetime import datetime

from app.domain.operations import (
    ScheduleInputs,
    SchedulePolicy,
    build_schedule_inputs,
    schedule_data_cycles,
)
from app.schemas.mission import MissionState
from app.schemas.operations import MissionSchedule
from app.services.catalog_service import CatalogService
from app.services.mission_service import MissionService, ValidationOutcome


@dataclass(frozen=True)
class ScheduleResult:
    inputs: ScheduleInputs
    schedule: MissionSchedule


@dataclass(frozen=True)
class ScheduleOutcome:
    result: ScheduleResult | None = None
    failure: ValidationOutcome | None = None


class ScheduleService:
    def __init__(self, missions: MissionService, catalogs: CatalogService) -> None:
        self._missions = missions
        self._catalogs = catalogs

    def schedule(
        self, state: MissionState, *, accept_data_loss: bool, now: datetime
    ) -> ScheduleOutcome:
        outcome = self._missions.validate(state, now)
        if outcome.analysis is None:
            return ScheduleOutcome(failure=outcome)
        inputs = build_schedule_inputs(state, outcome.analysis, self._catalogs.catalog)
        schedule = schedule_data_cycles(
            inputs.opportunities,
            inputs.contacts,
            inputs.resources,
            SchedulePolicy(accept_data_loss=accept_data_loss),
        )
        return ScheduleOutcome(result=ScheduleResult(inputs, schedule))

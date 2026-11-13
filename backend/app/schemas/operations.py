"""Operations contracts: data-cycle scheduling and onboard autonomy (architecture 19.5, 19.6).

Owner: operations algorithms owner. Times (`start`, `end`, `t`) are mission elapsed
seconds. Autonomy policies use architecture 19.5 names (decision D3) and live with
operations, not a separate autonomy package (decision D2).
"""

from typing import Literal, Self

from pydantic import StrictBool, model_validator

from app.schemas._frozen import FrozenContract
from app.schemas.api import ContractModel
from app.schemas.science_belief import BeliefState
from app.schemas.units import FiniteFloat, NonNegativeFloat

RejectionReason = Literal[
    "INSTRUMENT_CONFLICT",
    "ENERGY",
    "POINTING",
    "BUFFER_OVERFLOW_BEFORE_CONTACT",
    "NO_CONTACT",
    "PHASE",
    "THERMAL",
]
AutonomyPolicy = Literal["conservative", "science-first", "resource-aware"]


def _check_window(start: float, end: float) -> None:
    if end < start:
        raise ValueError("end must be >= start")


class ObservationOpportunity(ContractModel):
    id: str
    start: NonNegativeFloat
    end: NonNegativeFloat
    instrument_id: str
    expected_science_value: NonNegativeFloat
    generated_data_bits: NonNegativeFloat
    energy_joules: NonNegativeFloat
    slew_seconds: NonNegativeFloat
    compatible_attitude: str

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        _check_window(self.start, self.end)
        return self


class ContactWindow(ContractModel):
    id: str
    start: NonNegativeFloat
    end: NonNegativeFloat
    max_downlink_bits: NonNegativeFloat
    station_id: str
    link_margin_db: FiniteFloat

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        _check_window(self.start, self.end)
        return self


class ScheduledDataCycle(ContractModel):
    id: str
    observations: list[str]
    contact_window_id: str | None = None
    buffer_before_bits: NonNegativeFloat
    buffer_after_bits: NonNegativeFloat
    explanation: str


class RejectedOpportunity(ContractModel):
    id: str
    reason_code: RejectionReason


class BufferPoint(ContractModel):
    t: NonNegativeFloat
    bits: NonNegativeFloat


class MissionSchedule(ContractModel):
    accepted: list[str]
    rejected: list[RejectedOpportunity]
    cycles: list[ScheduledDataCycle]
    buffer_timeline: list[BufferPoint]
    # Architecture 19.6 step 5: data loss only with the player's explicit acceptance.
    data_loss_risk_accepted: StrictBool = False
    data_lost_bits: NonNegativeFloat = 0.0

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if set(self.accepted) & {r.id for r in self.rejected}:
            raise ValueError("an opportunity cannot be both accepted and rejected")
        if self.data_lost_bits > 0 and not self.data_loss_risk_accepted:
            raise ValueError("data_lost_bits > 0 requires data_loss_risk_accepted")
        return self


class AutonomyAction(ContractModel):
    id: str
    observation_id: str
    expected_science_value: NonNegativeFloat
    energy_joules: NonNegativeFloat
    data_bits: NonNegativeFloat
    risk: NonNegativeFloat
    slew_seconds: NonNegativeFloat


class ScoredAction(FrozenContract):
    action_id: str
    utility: FiniteFloat
    feasible: StrictBool
    rejection_reason: str | None = None


class AutonomyDecision(FrozenContract):
    decision_maker: Literal["ground", "onboard-policy"]
    policy: AutonomyPolicy
    belief: BeliefState  # input belief state the decision was made from (19.5)
    candidates: tuple[ScoredAction, ...]
    selected_action_id: str | None = None
    reason: str

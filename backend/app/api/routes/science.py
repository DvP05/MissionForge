"""Science belief route (Task 6.4): POST /api/science/belief.

The hidden scenario truth is drawn on the server from the mission seed and never appears
in a response; only observation outcomes (and the updated belief) are returned.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import Field, StrictInt

from app.api.deps import get_science_service
from app.api.errors import VALIDATION_ERROR, error_response
from app.domain.errors import DomainValidationError
from app.schemas.api import ApiMeta, ApiResult, ContractModel
from app.schemas.mission import MissionState
from app.schemas.science_belief import BeliefState, ObservationLikelihood, ScienceHypothesis
from app.schemas.units import FiniteFloat
from app.services.science_service import MAX_HISTORY, ObservedOutcome, ScienceService

DISCLAIMER = (
    "Conditional on the scenario model: the hypotheses and likelihood tables are authored "
    "gameplay estimates for an illustrative target, not claims about a real asteroid."
)

router = APIRouter()


class ObservationIn(ContractModel):
    instrument_id: str
    outcome_id: str


class BeliefRequest(ContractModel):
    mission_state: MissionState
    history: list[ObservationIn] = Field(default_factory=list, max_length=MAX_HISTORY)
    observe_with: str | None = None


class NextObservationOut(ContractModel):
    instrument_id: str
    expected_information_gain_bits: FiniteFloat
    outcome_probabilities: dict[str, FiniteFloat]


class BeliefData(ContractModel):
    mission_id: str
    design_revision: StrictInt
    model_version: str
    hypotheses: list[ScienceHypothesis]
    likelihoods: list[ObservationLikelihood]  # only for instruments on this spacecraft
    belief: BeliefState
    history: list[ObservationIn]
    last_outcome: ObservationIn | None
    next_observations: list[NextObservationOut]
    disclaimer: str


@router.post("/science/belief", response_model=ApiResult[BeliefData])
def science_belief(
    body: BeliefRequest,
    request: Request,
    service: Annotated[ScienceService, Depends(get_science_service)],
) -> ApiResult[BeliefData] | JSONResponse:
    """Bayesian belief over scenario hypotheses plus the most informative next observation."""
    try:
        result = service.belief(
            body.mission_state,
            [ObservedOutcome(h.instrument_id, h.outcome_id) for h in body.history],
            body.observe_with,
        )
    except LookupError:
        return error_response(
            request,
            404,
            "SCIENCE_MODEL_UNAVAILABLE",
            "This scenario has no science hypothesis model yet.",
        )
    except DomainValidationError as err:
        return error_response(
            request,
            422,
            VALIDATION_ERROR,
            "The observation history is not valid for this mission.",
            details={"code": err.code, "field": err.field},
        )
    selected = set(body.mission_state.architecture.instrument_ids)
    return ApiResult[BeliefData](
        ok=True,
        data=BeliefData(
            mission_id=body.mission_state.mission_id,
            design_revision=body.mission_state.design_revision,
            model_version=f"{result.model.scenario_id}@{result.model.version}",
            hypotheses=list(result.model.hypotheses),
            likelihoods=[t for t in result.model.likelihoods if t.instrument_id in selected],
            belief=result.belief,
            history=[
                ObservationIn(instrument_id=h.instrument_id, outcome_id=h.outcome_id)
                for h in result.history
            ],
            last_outcome=(
                ObservationIn(
                    instrument_id=result.last_outcome.instrument_id,
                    outcome_id=result.last_outcome.outcome_id,
                )
                if result.last_outcome
                else None
            ),
            next_observations=[
                NextObservationOut(
                    instrument_id=n.instrument_id,
                    expected_information_gain_bits=n.expected_information_gain_bits,
                    outcome_probabilities=n.outcome_probabilities,
                )
                for n in result.next_observations
            ],
            disclaimer=DISCLAIMER,
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )

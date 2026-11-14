from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import Field, StrictBool, StrictInt

from app.api.deps import Clock, get_clock, get_mission_service, get_simulation_service
from app.api.errors import CATALOG_ITEM_NOT_FOUND, VALIDATION_ERROR, error_response
from app.config import Settings, get_settings
from app.domain.errors import DomainValidationError
from app.domain.simulation.runner import LaunchBlocked
from app.schemas.analysis import MissionAnalysis
from app.schemas.api import ApiMeta, ApiResult, ContractModel
from app.schemas.mission import MissionState
from app.schemas.optimization import TradeStudyResult
from app.schemas.simulation import FinalReport, MissionEvent, MissionRun, TelemetrySample
from app.services.mission_service import DesignRef, MissionService, ValidationOutcome
from app.services.simulation_service import (
    DecisionAlreadyMadeError,
    RunNotFoundError,
    SimulationService,
    StoredRun,
)

MAX_TRADE_ALTERNATIVES = 3


class ValidateRequest(ContractModel):
    mission_state: MissionState


class ValidateData(ContractModel):
    analysis: MissionAnalysis


class TradeStudyRequest(ContractModel):
    base_mission_state: MissionState
    alternatives: Annotated[
        list[MissionState], Field(min_length=1, max_length=MAX_TRADE_ALTERNATIVES)
    ]


class SimulateRequest(ContractModel):
    mission_state: MissionState
    random_seed: StrictInt
    scenario_event_set_id: str | None = Field(default=None, min_length=1, max_length=100)
    experimental: StrictBool = False
    decisions: (
        dict[
            Annotated[str, Field(min_length=1, max_length=200)],
            Annotated[str, Field(min_length=1, max_length=200)],
        ]
        | None
    ) = Field(default=None, max_length=50)
    monte_carlo_samples: StrictInt | None = Field(default=None, ge=1)


class DecisionRequest(ContractModel):
    event_id: str = Field(min_length=1, max_length=200)
    choice_id: str = Field(min_length=1, max_length=200)


class SimulateData(ContractModel):
    """Architecture 11.2 shape. `telemetry`, `events` and `finalReport` are the very same
    objects as the `run` fields (convenience copies, never separately computed)."""

    analysis: MissionAnalysis
    run: MissionRun
    telemetry: tuple[TelemetrySample, ...]
    events: tuple[MissionEvent, ...]
    final_report: FinalReport
    notes: list[str] = Field(default_factory=list)


# Domain codes that are the caller's fault (422). Anything else is a server fault and stays a 500.
_CLIENT_DOMAIN_ERRORS: dict[str, str] = {
    "UNKNOWN_EVENT_SET": "The scenario event set does not exist.",
    "EVENT_SET_SCENARIO_MISMATCH": "The event set does not apply to this scenario.",
    "INVALID_CHOICE": "The chosen option does not exist for that decision.",
    "UNKNOWN_DECISION_EVENT": "That event is not a decision of this run (or it ended first).",
}

router = APIRouter()


def _failure_response(
    request: Request,
    settings: Settings,
    outcome: ValidationOutcome,
    design: DesignRef | None = None,
) -> JSONResponse:
    """Maps a failed validation outcome to the error envelope (R22); `design` tags trade studies."""
    extra = {"design": {"role": design.role, "index": design.index}} if design is not None else {}
    if outcome.missing_components:
        return error_response(
            request,
            422,
            CATALOG_ITEM_NOT_FOUND,
            "The design references catalogue components that do not exist.",
            details={
                "catalogVersion": settings.catalog_version,
                "items": [{"path": m.path, "id": m.id} for m in outcome.missing_components],
                **extra,
            },
        )
    return error_response(
        request,
        422,
        VALIDATION_ERROR,
        "The mission state is inconsistent.",
        details={"issues": [i.model_dump(by_alias=True) for i in outcome.issues], **extra},
    )


@router.post("/mission/validate", response_model=ApiResult[ValidateData])
def validate_mission(
    body: ValidateRequest,
    request: Request,
    service: Annotated[MissionService, Depends(get_mission_service)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApiResult[ValidateData] | JSONResponse:
    outcome = service.validate(body.mission_state, clock())
    if outcome.analysis is None:
        return _failure_response(request, settings, outcome)
    return ApiResult[ValidateData](
        ok=True,
        data=ValidateData(analysis=outcome.analysis),
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.post("/mission/trade-study", response_model=ApiResult[TradeStudyResult])
def trade_study(
    body: TradeStudyRequest,
    request: Request,
    service: Annotated[MissionService, Depends(get_mission_service)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApiResult[TradeStudyResult] | JSONResponse:
    """Compare 1-3 alternatives against a base design (architecture 11.2). Nothing is mutated."""
    outcome = service.trade_study(body.base_mission_state, body.alternatives, clock())
    if outcome.result is None:
        if outcome.failure is None or outcome.failed_design is None:
            raise RuntimeError("trade study returned neither a result nor a failure")
        return _failure_response(request, settings, outcome.failure, outcome.failed_design)
    return ApiResult[TradeStudyResult](
        ok=True, data=outcome.result, meta=ApiMeta(request_id=request.state.request_id)
    )


def _simulate_data(stored: StoredRun, notes: list[str] | None = None) -> SimulateData:
    run = stored.run
    return SimulateData(
        analysis=stored.sim_input.analysis,
        run=run,
        telemetry=run.telemetry,
        events=run.events,
        final_report=run.final_report,
        notes=notes or [],
    )


def _domain_failure(request: Request, exc: DomainValidationError) -> JSONResponse:
    if isinstance(exc, LaunchBlocked):
        return error_response(
            request,
            422,
            "LAUNCH_BLOCKED",
            "Launch is blocked: the design fails hard constraints. "
            "Fix them, or run it as an experimental what-if.",
            details={"failingConstraintIds": list(exc.failing_constraint_ids)},
        )
    message = _CLIENT_DOMAIN_ERRORS.get(exc.code)
    if message is None:
        raise exc
    return error_response(request, 422, exc.code, message, details={"field": exc.field})


def _run_not_found(request: Request) -> JSONResponse:
    return error_response(
        request,
        404,
        "RUN_NOT_FOUND",
        "That run is not available. Runs are kept in memory only and may have been evicted; "
        "run the simulation again.",
    )


@router.post("/mission/simulate", response_model=ApiResult[SimulateData])
def simulate_mission(
    body: SimulateRequest,
    request: Request,
    service: Annotated[SimulationService, Depends(get_simulation_service)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApiResult[SimulateData] | JSONResponse:
    """Run one deterministic simulation (architecture 11.2). Never accepts a client analysis."""
    cap = settings.max_monte_carlo_samples
    if body.monte_carlo_samples is not None and body.monte_carlo_samples > cap:
        return error_response(
            request,
            422,
            "SIMULATION_LIMIT_EXCEEDED",
            f"monteCarloSamples exceeds the limit of {cap}.",
            details={"maxSamples": cap, "requested": body.monte_carlo_samples},
        )
    try:
        outcome = service.simulate(
            body.mission_state,
            seed=body.random_seed,
            event_set_id=body.scenario_event_set_id,
            experimental=body.experimental,
            decisions=body.decisions or {},
            now=clock(),
        )
    except DomainValidationError as exc:
        return _domain_failure(request, exc)
    if outcome.stored is None:
        if outcome.failure is None:
            raise RuntimeError("simulation returned neither a run nor a failure")
        return _failure_response(request, settings, outcome.failure)
    notes: list[str] = []
    if body.monte_carlo_samples is not None:
        notes.append(
            "Monte Carlo sampling is not available yet; monteCarloSamples was accepted and "
            "ignored. This is a single deterministic run."
        )
    return ApiResult[SimulateData](
        ok=True,
        data=_simulate_data(outcome.stored, notes),
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.post("/mission/run/{run_id}/decision", response_model=ApiResult[SimulateData])
def decide(
    run_id: str,
    body: DecisionRequest,
    request: Request,
    service: Annotated[SimulationService, Depends(get_simulation_service)],
) -> ApiResult[SimulateData] | JSONResponse:
    """Branch a stored run with one player decision. Returns a NEW run; the source is unchanged."""
    try:
        stored = service.decide(run_id, body.event_id, body.choice_id)
    except RunNotFoundError:
        return _run_not_found(request)
    except DecisionAlreadyMadeError:
        return error_response(
            request,
            409,
            "DECISION_ALREADY_MADE",
            "That decision was already made in this run. Runs are immutable; "
            "branch from an earlier run to choose differently.",
            details={"eventId": body.event_id},
        )
    except DomainValidationError as exc:
        return _domain_failure(request, exc)
    return ApiResult[SimulateData](
        ok=True, data=_simulate_data(stored), meta=ApiMeta(request_id=request.state.request_id)
    )


@router.get("/mission/run/{run_id}", response_model=ApiResult[SimulateData])
def get_run(
    run_id: str,
    request: Request,
    service: Annotated[SimulationService, Depends(get_simulation_service)],
) -> ApiResult[SimulateData] | JSONResponse:
    """A stored run (Mission Control reload). 404 once evicted; the client keeps its own copy."""
    try:
        stored = service.get(run_id)
    except RunNotFoundError:
        return _run_not_found(request)
    return ApiResult[SimulateData](
        ok=True, data=_simulate_data(stored), meta=ApiMeta(request_id=request.state.request_id)
    )

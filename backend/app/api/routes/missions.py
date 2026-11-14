import json
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import Field, StrictBool, StrictInt, ValidationError

from app.api.deps import Clock, get_clock, get_mission_service, get_simulation_service
from app.api.errors import (
    CATALOG_ITEM_NOT_FOUND,
    VALIDATION_ERROR,
    error_response,
    validation_fields_from_pydantic,
)
from app.config import Settings, get_settings
from app.domain.dossier.export_mission_dossier import ReplayCheck, export_mission_dossier
from app.domain.errors import DomainValidationError
from app.domain.mission.migrations import migrate_mission
from app.domain.simulation.runner import LaunchBlocked
from app.schemas.analysis import MissionAnalysis
from app.schemas.api import ApiMeta, ApiResult, ContractModel
from app.schemas.evidence import MissionPackage
from app.schemas.mission import MissionState
from app.schemas.optimization import TradeStudyResult
from app.schemas.simulation import FinalReport, MissionEvent, MissionRun, TelemetrySample
from app.services.mission_service import DesignRef, MissionService, ValidationOutcome
from app.services.simulation_service import (
    DecisionAlreadyMadeError,
    RunNotFoundError,
    SimulationService,
    StoredRun,
    VersionMismatch,
)

MAX_TRADE_ALTERNATIVES = 3
MAX_PACKAGE_RUNS = 20
SUPPORTED_PACKAGE_VERSION = "1.0"


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


class VersionMismatchItem(ContractModel):
    field: str
    recorded: str
    current: str


class RunReplayStatus(ContractModel):
    """Per imported run: do the recorded versions match this server (so a replay can be verified)?

    Versions only, nothing is re-run: "replayable" is never a claim of identity.
    """

    run_id: str
    status: Literal["replayable", "version-mismatch"]
    mismatches: list[VersionMismatchItem]
    # The run's design re-analysed by THIS engine (derived, may differ from the recorded
    # run when versions differ). Null when the design no longer validates here.
    analysis: MissionAnalysis | None = None


class ImportData(ContractModel):
    package: MissionPackage
    replay: list[RunReplayStatus]


class ReplayRequest(ContractModel):
    run: MissionRun


class ReplayData(ContractModel):
    identical: bool
    status: Literal["identical-replay", "version-mismatch", "diverged"]
    mismatches: list[VersionMismatchItem]
    run: MissionRun | None = None


class DossierRequest(ContractModel):
    run: MissionRun


class DossierData(ContractModel):
    """The Evidence Passport: the JSON package (re-importable) and the self-contained HTML."""

    package: MissionPackage
    html: str
    # Structured replay result of the server-side check (the UI must use this, never the HTML).
    replay_status: Literal["identical-replay", "version-mismatch", "diverged"]
    replay_mismatches: list[str]


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
                "catalogVersion": request.app.state.catalog_service.version,
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


def _mismatch_items(items: tuple[VersionMismatch, ...] | list[VersionMismatch]) -> list[Any]:
    return [
        VersionMismatchItem(field=m.field, recorded=m.recorded, current=m.current) for m in items
    ]


def _reject_constant(name: str) -> Any:
    raise ValueError(f"non-standard JSON constant {name}")


@router.post("/mission/import", response_model=ApiResult[ImportData])
async def import_package(
    request: Request,
    service: Annotated[SimulationService, Depends(get_simulation_service)],
    missions: Annotated[MissionService, Depends(get_mission_service)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApiResult[ImportData] | JSONResponse:
    """Validate an exported MissionPackage (architecture 13, 16). Body = the raw package JSON.

    All-or-nothing: nothing is stored server-side and any failure returns an error envelope,
    so the client replaces its saved state only on ok=true. Titles are sanitised by the
    schema; the analysis is recomputed here (the exported one is derived, never trusted).
    """
    body = await request.body()
    try:
        raw = json.loads(body, parse_constant=_reject_constant)
    except (ValueError, RecursionError):
        return error_response(
            request,
            422,
            "INVALID_JSON",
            "The file is not valid JSON (NaN, Infinity and malformed text are rejected).",
        )
    if not isinstance(raw, dict):
        return error_response(
            request, 422, "INVALID_PACKAGE", "A mission package must be a JSON object."
        )
    version = raw.get("packageSchemaVersion", raw.get("package_schema_version"))
    if version != SUPPORTED_PACKAGE_VERSION:
        return error_response(
            request,
            422,
            "UNSUPPORTED_PACKAGE_VERSION",
            "This package uses a package format this version cannot read, and it is not "
            f"guessed at. Supported package version: {SUPPORTED_PACKAGE_VERSION}.",
            details={"supported": SUPPORTED_PACKAGE_VERSION, "found": str(version)[:40]},
        )
    mission_raw = raw.get("mission")
    if not isinstance(mission_raw, dict):
        return error_response(
            request,
            422,
            "INVALID_PACKAGE",
            "The package has no mission object.",
            details={"fields": [{"path": "mission", "message": "required", "type": "missing"}]},
        )
    try:
        raw["mission"] = migrate_mission(mission_raw)
    except DomainValidationError as exc:
        return error_response(
            request,
            422,
            exc.code,
            "The mission schema version in this package is not supported; it is not "
            "silently reinterpreted.",
            details={"field": exc.field, "supported": "1.0"},
        )
    runs_raw = raw.get("runs")
    if isinstance(runs_raw, list) and len(runs_raw) > MAX_PACKAGE_RUNS:
        return error_response(
            request,
            422,
            "PACKAGE_TOO_MANY_RUNS",
            f"A package may contain at most {MAX_PACKAGE_RUNS} runs.",
            details={"max": MAX_PACKAGE_RUNS},
        )
    try:
        package = MissionPackage.model_validate(raw)
    except ValidationError as exc:
        return error_response(
            request,
            422,
            "INVALID_PACKAGE",
            "The package does not match the mission package format.",
            details={"fields": validation_fields_from_pydantic(exc)},
        )
    run_ids = [r.run_id for r in package.runs]
    if len(set(run_ids)) != len(run_ids):
        return error_response(
            request, 422, "INVALID_PACKAGE", "The package contains duplicate run ids."
        )
    now = clock()
    outcome = missions.validate(package.mission, now)
    if outcome.analysis is None:
        return _failure_response(request, settings, outcome)
    package.latest_analysis = outcome.analysis  # derived: always recomputed on import
    statuses: list[RunReplayStatus] = []
    for run in package.runs:
        mismatches = service.version_mismatches(run)
        analysis = service.run_analysis(run, now).analysis
        if analysis is None and not mismatches:
            mismatches = [VersionMismatch("design", "valid", "fails validation in this catalogue")]
        statuses.append(
            RunReplayStatus(
                run_id=run.run_id,
                status="version-mismatch" if mismatches else "replayable",
                mismatches=_mismatch_items(mismatches),
                analysis=analysis,
            )
        )
    return ApiResult[ImportData](
        ok=True,
        data=ImportData(package=package, replay=statuses),
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.post("/mission/replay", response_model=ApiResult[ReplayData])
def replay_run(
    body: ReplayRequest,
    request: Request,
    service: Annotated[SimulationService, Depends(get_simulation_service)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ApiResult[ReplayData]:
    """Replay a recorded run. `identical` is true only after comparing the re-run with the
    recorded run (canonical JSON; numbers compare by value, as 275 vs 275.0 after a JS round trip).

    Differing engine / catalogue / scenario / schema versions or a missing event set return
    ok=true with status "version-mismatch" and no re-run: never a claim of identity.
    """
    outcome = service.replay(body.run, clock())
    return ApiResult[ReplayData](
        ok=True,
        data=ReplayData(
            identical=outcome.identical,
            status=outcome.status,
            mismatches=_mismatch_items(outcome.mismatches),
            run=outcome.run,
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.post("/mission/dossier", response_model=ApiResult[DossierData])
def export_dossier(
    body: DossierRequest,
    request: Request,
    service: Annotated[SimulationService, Depends(get_simulation_service)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApiResult[DossierData]:
    """Evidence Passport v1 (architecture 19.9). The run is re-validated by the schema; the
    budgets are recomputed here from its snapshot and the replay is re-checked here, so the
    passport never relies on client-calculated analysis or a client claim of identity.
    """
    now = clock()
    run = body.run
    analysis = service.run_analysis(run, now).analysis
    replay = service.replay(run, now)
    dossier = export_mission_dossier(
        run,
        service.catalog,
        exported_at=now,
        app_version=settings.app_version,
        analysis=analysis,
        replay=ReplayCheck(
            replay.status,
            tuple(m.field for m in replay.mismatches),
        ),
    )
    return ApiResult[DossierData](
        ok=True,
        data=DossierData(
            package=dossier.package,
            html=dossier.html,
            replay_status=replay.status,
            replay_mismatches=[m.field for m in replay.mismatches],
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )

"""Mission Design Arena route (Task 6.2): POST /api/mission/optimize.

The domain returns the full OptimizationResult contract (each candidate carries its whole
MissionState and MissionAnalysis, about 35 kB each). Sending 250 of those to a browser is
about 9 MB, so this route returns a projection: the candidate's architecture plus the
numbers the Arena plots. The browser rebuilds a candidate as "current mission with this
architecture" and re-validates it through the normal analysis path when it is loaded.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import Field, StrictBool, StrictInt

from app.api.deps import Clock, get_clock, get_optimization_service
from app.api.routes.missions import _failure_response
from app.config import Settings, get_settings
from app.domain.optimization import MAX_CANDIDATES
from app.domain.optimization.optimize import MAX_RESILIENCE_SAMPLES
from app.schemas.analysis import Feasibility
from app.schemas.api import ApiMeta, ApiResult, ContractModel
from app.schemas.mission import MissionState, SpacecraftArchitecture
from app.schemas.optimization import Archetype, ArchitectureCandidate, OptimizationObjective
from app.schemas.units import FiniteFloat
from app.services.optimization_service import OptimizationService

DEFAULT_CANDIDATES = 150
DEFAULT_RESILIENCE_SAMPLES = 20

router = APIRouter()


class OptimizeRequest(ContractModel):
    mission_state: MissionState
    seed: StrictInt | None = None  # defaults to the mission's random_seed
    cap: StrictInt = Field(default=DEFAULT_CANDIDATES, ge=10, le=MAX_CANDIDATES)
    robustness_samples: StrictInt = Field(
        default=DEFAULT_RESILIENCE_SAMPLES, ge=0, le=MAX_RESILIENCE_SAMPLES
    )


class CandidateSummary(ContractModel):
    id: str
    generation: StrictInt
    feasible: StrictBool
    feasibility: Feasibility
    architecture: SpacecraftArchitecture
    objective_vector: dict[str, FiniteFloat]
    estimated_cost_usd: FiniteFloat
    dry_mass_kg: FiniteFloat
    science_coverage_score: FiniteFloat
    returned_fraction: FiniteFloat
    score_total: FiniteFloat
    failed_constraints: list[str]
    explanation: list[str]


class OptimizeData(ContractModel):
    mission_id: str
    design_revision: StrictInt
    seed: StrictInt
    objectives: list[OptimizationObjective]
    candidates: list[CandidateSummary]
    pareto_front_ids: list[str]
    archetypes: dict[Archetype, str]
    near_misses: list[str]


def _summary(c: ArchitectureCandidate) -> CandidateSummary:
    a = c.analysis
    return CandidateSummary(
        id=c.id,
        generation=c.generation,
        feasible=c.feasible,
        feasibility=a.feasibility,
        architecture=c.mission_state.architecture,
        objective_vector=c.objective_vector,
        estimated_cost_usd=float(a.budgets.estimated_cost_usd.value),
        dry_mass_kg=float(a.budgets.dry_mass_kg.value),
        science_coverage_score=a.science.coverage_score,
        returned_fraction=a.science.returned_fraction,
        score_total=a.score.total,
        failed_constraints=[x.id for x in a.constraints if x.status == "fail"],
        explanation=c.explanation,
    )


@router.post("/mission/optimize", response_model=ApiResult[OptimizeData])
def mission_optimize(
    body: OptimizeRequest,
    request: Request,
    service: Annotated[OptimizationService, Depends(get_optimization_service)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApiResult[OptimizeData] | JSONResponse:
    """Candidate designs, the feasible Pareto front, archetypes and near misses (19.2)."""
    seed = body.seed if body.seed is not None else body.mission_state.random_seed
    outcome = service.optimize(
        body.mission_state,
        seed=seed,
        cap=body.cap,
        robustness_samples=body.robustness_samples,
        now=clock(),
    )
    if outcome.result is None:
        if outcome.failure is None:
            raise RuntimeError("optimize returned neither a result nor a failure")
        return _failure_response(request, settings, outcome.failure)
    r = outcome.result
    return ApiResult[OptimizeData](
        ok=True,
        data=OptimizeData(
            mission_id=body.mission_state.mission_id,
            design_revision=body.mission_state.design_revision,
            seed=r.seed,
            objectives=r.objectives,
            candidates=[_summary(c) for c in r.candidates],
            pareto_front_ids=r.pareto_front_ids,
            archetypes=r.archetypes,
            near_misses=r.near_misses,
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )

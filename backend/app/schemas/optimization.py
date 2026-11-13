"""Architecture graph, trade-study and Pareto/arena contracts (architecture 8.4, 19.1, 19.2).

Owner: algorithms lead. Objective vectors are minimisation-normalised; hard constraints
stay outside the objective vector (see MissionAnalysis.constraints / feasibility).
"""

from typing import Literal

from pydantic import Field, StrictBool, StrictInt

from app.schemas.analysis import MissionAnalysis
from app.schemas.api import ContractModel
from app.schemas.mission import MissionState
from app.schemas.units import FiniteFloat, Scalar

ArchitectureNodeKind = Literal[
    "science-objective", "measurement-requirement", "instrument",
    "spacecraft-subsystem", "launch-option", "trajectory-option",
    "observation-task", "contact-window", "science-product",
]  # fmt: skip
ArchitectureEdgeKind = Literal[
    "satisfies", "allocated-to", "depends-on", "consumes",
    "generates", "constrains", "downlinks-through",
]  # fmt: skip
ObjectiveKey = Literal[
    "lifecycle_cost", "dry_mass", "duration_days",
    "negative_science_return", "negative_robustness",
]  # fmt: skip
Archetype = Literal["lean", "science-max", "resilient"]


class ArchitectureNode(ContractModel):
    id: str
    kind: ArchitectureNodeKind
    label: str
    entity_id: str | None = None
    attributes: dict[str, Scalar] = Field(default_factory=dict)


class ArchitectureEdge(ContractModel):
    id: str
    from_id: str
    to_id: str
    kind: ArchitectureEdgeKind
    rationale: str


class OptimizationObjective(ContractModel):
    key: ObjectiveKey
    direction: Literal["minimize", "maximize"]
    weight: FiniteFloat | None = None  # ranking preference only, never Pareto dominance


class ArchitectureCandidate(ContractModel):
    id: str
    mission_state: MissionState
    analysis: MissionAnalysis
    objective_vector: dict[str, FiniteFloat]
    feasible: StrictBool
    generation: StrictInt = Field(ge=0)
    explanation: list[str]


class TradeAlternative(ContractModel):
    analysis: MissionAnalysis
    deltas: dict[str, FiniteFloat]  # metric -> (alternative - base), SI units


class TradeStudyResult(ContractModel):
    base_analysis: MissionAnalysis
    alternatives: list[TradeAlternative]


class OptimizationResult(ContractModel):
    seed: StrictInt
    objectives: list[OptimizationObjective]
    candidates: list[ArchitectureCandidate]
    pareto_front_ids: list[str]  # ids into `candidates`; feasible only
    archetypes: dict[Archetype, str]  # archetype -> candidate id
    near_misses: list[str]  # ids into `candidates`; hard-infeasible, shown separately

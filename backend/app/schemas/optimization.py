"""Architecture graph, trade-study and Pareto/arena contracts (architecture 8.4, 19.1, 19.2).

Owner: algorithms lead. Objective vectors are minimisation-normalised; hard constraints
stay outside the objective vector (see MissionAnalysis.constraints / feasibility).
"""

from typing import Literal, Self

from pydantic import Field, StrictBool, StrictInt, model_validator

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


class ArchitectureGraph(ContractModel):
    """Typed directed mission graph (19.1); a projection of canonical state, never edited."""

    nodes: list[ArchitectureNode]
    edges: list[ArchitectureEdge]

    @model_validator(mode="after")
    def _edges_reference_nodes(self) -> Self:
        ids = [n.id for n in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate node id")
        known = set(ids)
        if any(e.from_id not in known or e.to_id not in known for e in self.edges):
            raise ValueError("edge references an unknown node")
        return self


# Science / mission traceability matrix rows (STM / MTM, 19.1); shared by the graph route
# and Evidence Passport v2.
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


class MetricChange(ContractModel):
    metric: str
    # None = undefined / not-modelled at that revision (R38: never a fake 0).
    before: FiniteFloat | None
    after: FiniteFloat | None
    unit: str


class ImpactReport(ContractModel):
    """Effect of one design edit (19.1 behaviour 7)."""

    changed_metrics: list[MetricChange]
    newly_violated: list[str]  # constraint ids that now fail / warn
    improved: list[str]  # constraint ids that improved
    affected_objectives: list[str]  # science objective ids


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

    @model_validator(mode="after")
    def _ids_reference_candidates(self) -> Self:
        known = {c.id for c in self.candidates}
        referenced = set(self.pareto_front_ids) | set(self.near_misses)
        if not referenced | set(self.archetypes.values()) <= known:
            raise ValueError("pareto_front_ids, archetypes and near_misses must be candidate ids")
        if set(self.pareto_front_ids) & set(self.near_misses):
            raise ValueError("a near miss cannot be on the Pareto front")
        return self

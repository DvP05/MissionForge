"""Mission simulation contracts (architecture 9.2, 9.3, 9.6, 19.5, 19.9; module_breakdown 4.2C).

Owner: simulation lead + integration lead.

Every model reachable from MissionRun is deeply immutable: `FrozenContract` (assignment
raises, nested instances are revalidated copies, never aliases), tuples for collections and
`FrozenMap` for maps. A completed run therefore cannot be mutated and is hashable.
MissionRun carries its exact input snapshot and run manifest so it can be replayed from a
MissionPackage even after the design moved to a later revision.
"""

from typing import Literal, Self

from pydantic import Field, StrictBool, StrictInt, model_validator

from app.schemas._frozen import FrozenContract, FrozenMap
from app.schemas.analysis import MissionAnalysis, ScoreBreakdown
from app.schemas.api import ContractModel
from app.schemas.mission import MissionState
from app.schemas.operations import AutonomyDecision
from app.schemas.units import Fidelity, FiniteFloat, NonNegativeFloat, Scalar, Unit, UnitFraction

Phase = Literal[
    "pre-launch",
    "launch-deployment",
    "commissioning",
    "cruise",
    "mid-course",
    "approach",
    "science-ops",
    "downlink-return",
    "complete",
    "terminated",
]
EventType = Literal["milestone", "telemetry", "anomaly", "decision", "science", "downlink"]
EventSeverity = Literal["info", "warning", "critical"]
# Who made a recorded decision (architecture 19.5 plus the interactive player).
DecisionMaker = Literal["ground", "onboard-policy", "player"]
# Who caused / resolved an event; "system" covers deterministic engine rules.
EventDecisionMaker = Literal["ground", "onboard-policy", "player", "system"]


class DecisionChoice(FrozenContract):
    id: str
    label: str
    tradeoff: str
    effects: FrozenMap[FiniteFloat] = Field(default_factory=FrozenMap)


class MissionEvent(FrozenContract):
    id: str
    sequence: StrictInt = Field(ge=0)
    mission_day: NonNegativeFloat
    phase: Phase
    type: EventType
    severity: EventSeverity
    title: str
    description: str
    trigger: FrozenMap[Scalar]
    choices: tuple[DecisionChoice, ...] = ()
    resolved_by: str | None = None
    decision_maker: EventDecisionMaker | None = None


class TelemetrySample(FrozenContract):
    channel: str
    unit: Unit
    mission_day: NonNegativeFloat
    value: FiniteFloat
    fidelity: Fidelity
    phase: Phase


class DecisionRecord(FrozenContract):
    event_id: str
    choice_id: str
    decision_maker: DecisionMaker
    mission_day: NonNegativeFloat
    rationale: str


class ScienceOutcome(FrozenContract):
    objective_id: str
    collected_fraction: UnitFraction
    returned_fraction: UnitFraction
    status: Literal["achieved", "partial", "missed"]


class PhaseTransition(FrozenContract):
    phase: Phase  # phase entered
    mission_day: NonNegativeFloat


class FinalReport(FrozenContract):
    outcome: Literal["success", "partial", "failure", "terminated"]
    summary: str
    score: ScoreBreakdown
    realized_risks: tuple[str, ...]
    root_causes: tuple[str, ...]
    counterfactuals: tuple[str, ...]
    limitations: tuple[str, ...]


class MissionRunManifest(FrozenContract):
    """Replay manifest (architecture 19.9). Re-exported by app.schemas.evidence.

    Versions are plain strings so an imported run made with a different engine /
    catalogue version stays representable and can be flagged "not identical replay".
    """

    schema_version: str
    engine_version: str
    catalog_version: str
    scenario_version: str
    event_set_id: str
    seed: StrictInt
    app_version: str


class MissionRun(FrozenContract):
    run_id: str
    mission_id: str
    design_revision: StrictInt = Field(ge=0)
    seed: StrictInt
    scenario_event_set_id: str
    engine_version: str
    catalog_version: str
    experimental: StrictBool
    input_snapshot: MissionState
    manifest: MissionRunManifest
    phases: tuple[Phase, ...]
    phase_transitions: tuple[PhaseTransition, ...]
    events: tuple[MissionEvent, ...]
    telemetry: tuple[TelemetrySample, ...]
    decisions: tuple[DecisionRecord, ...]
    autonomy_log: tuple[AutonomyDecision, ...] = ()
    science_outcomes: tuple[ScienceOutcome, ...]
    final_report: FinalReport

    @model_validator(mode="after")
    def _consistent_inputs(self) -> Self:
        snap, man = self.input_snapshot, self.manifest
        if snap.mission_id != self.mission_id or snap.design_revision != self.design_revision:
            raise ValueError("input_snapshot must match mission_id and design_revision")
        if (
            man.seed != self.seed
            or man.engine_version != self.engine_version
            or man.catalog_version != self.catalog_version
            or man.event_set_id != self.scenario_event_set_id
            or man.schema_version != snap.schema_version
        ):
            raise ValueError("manifest must match the run's seed, versions and event set")
        days = [t.mission_day for t in self.phase_transitions]
        if days != sorted(days):
            raise ValueError("phase_transitions must be ordered by mission_day")
        return self


class SimulationInput(ContractModel):
    mission_state: MissionState
    analysis: MissionAnalysis
    engine_version: str
    catalog_version: str
    random_seed: StrictInt
    scenario_event_set_id: str
    monte_carlo_samples: StrictInt | None = Field(default=None, ge=1)
    experimental: StrictBool = False

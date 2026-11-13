"""Mission simulation contracts (architecture 9.2, 9.3, 9.6; module_breakdown 4.2C).

Owner: simulation lead + integration lead.

Simulation output models are frozen and use tuples for collections so a completed
MissionRun cannot be mutated (append-only during the run, immutable afterwards).
"""

from typing import Literal

from pydantic import ConfigDict, Field, StrictBool, StrictInt

from app.schemas.analysis import MissionAnalysis, ScoreBreakdown
from app.schemas.api import ContractModel
from app.schemas.mission import MissionState
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


class _FrozenContract(ContractModel):
    model_config = ConfigDict(frozen=True)


class DecisionChoice(_FrozenContract):
    id: str
    label: str
    tradeoff: str
    effects: dict[str, FiniteFloat] = Field(default_factory=dict)


class MissionEvent(_FrozenContract):
    id: str
    sequence: StrictInt = Field(ge=0)
    mission_day: NonNegativeFloat
    phase: Phase
    type: EventType
    severity: EventSeverity
    title: str
    description: str
    trigger: dict[str, Scalar]
    choices: tuple[DecisionChoice, ...] = ()
    resolved_by: str | None = None
    decision_maker: EventDecisionMaker | None = None


class TelemetrySample(_FrozenContract):
    channel: str
    unit: Unit
    mission_day: NonNegativeFloat
    value: FiniteFloat
    fidelity: Fidelity
    phase: Phase


class DecisionRecord(_FrozenContract):
    event_id: str
    choice_id: str
    decision_maker: DecisionMaker
    mission_day: NonNegativeFloat
    rationale: str


class ScienceOutcome(_FrozenContract):
    objective_id: str
    collected_fraction: UnitFraction
    returned_fraction: UnitFraction
    status: Literal["achieved", "partial", "missed"]


class FinalReport(_FrozenContract):
    outcome: Literal["success", "partial", "failure", "terminated"]
    summary: str
    score: ScoreBreakdown
    root_causes: tuple[str, ...]
    counterfactuals: tuple[str, ...]
    limitations: tuple[str, ...]


class MissionRun(_FrozenContract):
    run_id: str
    mission_id: str
    design_revision: StrictInt = Field(ge=0)
    seed: StrictInt
    scenario_event_set_id: str
    engine_version: str
    catalog_version: str
    experimental: StrictBool
    phases: tuple[Phase, ...]
    events: tuple[MissionEvent, ...]
    telemetry: tuple[TelemetrySample, ...]
    decisions: tuple[DecisionRecord, ...]
    science_outcomes: tuple[ScienceOutcome, ...]
    final_report: FinalReport


class SimulationInput(ContractModel):
    mission_state: MissionState
    analysis: MissionAnalysis
    engine_version: str
    catalog_version: str
    random_seed: StrictInt
    scenario_event_set_id: str
    monte_carlo_samples: StrictInt | None = Field(default=None, ge=1)

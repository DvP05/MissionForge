"""Already-computed discipline results handed to constraints and scoring (Task 2.7).

``AnalysisContext`` is domain-internal (not an API contract). The orchestrator (Task 2.8)
builds it once per analysis; ``constraints``, ``score`` and ``drivers`` only read it, so
no discipline is recomputed and hard feasibility stays separate from the weighted score.
"""

from dataclasses import dataclass

from app.domain.analysis.comms import LinkResult
from app.domain.analysis.cost import CostBreakdown
from app.domain.analysis.data import DataLedger
from app.domain.analysis.mass import MassResult
from app.domain.analysis.power import EnergyLedger
from app.domain.analysis.propulsion import ManeuverBudget
from app.domain.catalog.compat import CompatibilityIssue
from app.schemas.analysis import ConstraintResult, ReliabilityAnalysis, ScienceAnalysis
from app.schemas.mission import MissionConstraints

# Gameplay constant (not source-backed): usable fraction of battery energy delivered to the
# loads. Used by the orchestrator (Task 2.8) when building the Battery for energy_ledger.
BATTERY_DISCHARGE_EFFICIENCY = 0.95


@dataclass(frozen=True)
class AnalysisContext:
    limits: MissionConstraints
    mass: MassResult
    maneuvers: ManeuverBudget
    avg_power_w: float
    peak_power_w: float
    # regulated peak supply of the phase whose peak-vs-supply margin is worst
    supply_power_w: float
    energy: EnergyLedger
    data: DataLedger
    buffer_capacity_bits: float
    # one per planned downlink contact, at min(planned rate, radio max rate) (R19)
    contact_links: tuple[LinkResult, ...]
    science: ScienceAnalysis
    science_missing: tuple[tuple[str, str], ...]  # (requirement id, reason) from science.py
    cost: CostBreakdown
    reliability: ReliabilityAnalysis
    thermal: ConstraintResult
    compat_issues: tuple[CompatibilityIssue, ...]
    trajectory_valid: bool
    overflow_accepted: bool = False  # player explicitly accepted buffer data loss
    required_measurement_ids: tuple[str, ...] = ()  # mandatory measurements in the mission
    pointing_ok: bool = True  # ADCS meets instrument pointing needs (as passed to science)
    power_ok: bool = True  # instruments can be powered (as passed to science)

"""Builders for constraint/score tests: a healthy AnalysisContext with per-field overrides."""

from dataclasses import replace
from typing import Any

from app.domain.analysis.comms import LinkResult
from app.domain.analysis.context import AnalysisContext
from app.domain.analysis.cost import CostBreakdown
from app.domain.analysis.data import ContactResult, DataLedger
from app.domain.analysis.mass import MassResult
from app.domain.analysis.power import EnergyLedger, PhaseEnergy
from app.domain.analysis.propulsion import ManeuverBudget
from app.schemas.analysis import ConstraintResult, ReliabilityAnalysis, ScienceAnalysis
from app.schemas.mission import MissionConstraints


def limits(**over: Any) -> MissionConstraints:
    base: dict[str, Any] = {
        "maximum_budget_usd": 100.0e6,
        "launch_mass_limit_kg": 500.0,
        "mass_margin_fraction": 0.1,
        "power_margin_fraction": 0.1,
        "data_margin_fraction": 0.2,
        "delta_v_margin_km_per_s": 0.1,
    }
    base.update(over)
    return MissionConstraints.model_validate(base)


def link(margin_db: float = 6.0) -> LinkResult:
    return LinkResult(0, 0, 0, 0, 0, 0, margin_db, 1000.0)


def ledger(gen_wh: float = 1000.0, cons_wh: float = 500.0, min_soc: float = 0.8) -> EnergyLedger:
    ph = PhaseEnergy("cruise", 3600.0, gen_wh, cons_wh, 100.0, 100.0, min_soc, 0.0)
    return EnergyLedger(
        per_phase=(ph,),
        min_soc_fraction=min_soc,
        soc_floor_fraction=0.2,
        closes=min_soc >= 0.2,
    )


def data(
    generated: float = 1.0e6,
    downlinked: float = 1.0e6,
    capacity: float = 2.0e6,
    peak: float = 1.0e5,
    overflow: float = 0.0,
) -> DataLedger:
    return DataLedger(
        generated_bits=generated,
        downlinked_bits=downlinked,
        buffer_timeline=(),
        peak_buffer_bits=peak,
        overflow_bits=overflow,
        margin_fraction=(downlinked - generated) / generated if generated else 0.0,
        per_contact=(ContactResult(0.0, 1000.0, capacity, downlinked),),
    )


def thermal_ok() -> ConstraintResult:
    return ConstraintResult(
        id="thermal", label="Thermal control", status="not-modelled", severity=0,
        explanation="qualitative check only",
    )  # fmt: skip


def science(score: float = 80.0) -> ScienceAnalysis:
    return ScienceAnalysis(
        coverage_score=score,
        weighted_objective_coverage={"o1": score / 100.0},
        missing_requirements=[],
        collected_fraction=score / 100.0,
        returned_fraction=score / 100.0,
    )


def cost(total: float) -> CostBreakdown:
    return CostBreakdown(
        hardware=1.0, launch=1.0, operations=1.0, ground=1.0, reserves=1.0, development=1.0,
        total=total, low=total, high=total,
    )  # fmt: skip


def make_ctx(**over: Any) -> AnalysisContext:
    """A healthy design: every constraint passes (thermal not-modelled)."""
    base = AnalysisContext(
        limits=limits(),
        mass=MassResult(
            payload_kg=20.0, subsystem_dry_kg=180.0, dry_kg=200.0, wet_kg=300.0,
            allocated_kg=330.0, margin_to_limit_fraction=0.34, top_contributors=(),
        ),
        maneuvers=ManeuverBudget(
            available_ms=2000.0, required_ms=1000.0, margin_ms=900.0, per_maneuver=(),
            reserve_consumed_by=None, informational=(),
        ),
        avg_power_w=50.0,
        peak_power_w=80.0,
        supply_power_w=200.0,
        energy=ledger(),
        data=data(),
        buffer_capacity_bits=1.0e6,
        contact_links=(link(), link()),
        science=science(),
        science_missing=(),
        cost=cost(50.0e6),
        reliability=ReliabilityAnalysis(
            nominal_reliability=0.9, risk_index=0.1, single_point_failures=[]
        ),
        thermal=thermal_ok(),
        compat_issues=(),
        trajectory_valid=True,
        required_measurement_ids=("m1",),
    )  # fmt: skip
    return replace(base, **over)

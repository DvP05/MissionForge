"""Shared builders for the Interface v1 contract tests.

Every public contract model gets a realistic minimal instance here. `BUILDERS` maps
"<module>.<Model>" to a zero-argument factory. Tests that request the
`contract_name` fixture are parametrised over every key (see pytest_generate_tests).
"""

from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

import pytest
from pydantic import BaseModel

from app.schemas import (
    analysis,
    catalog,
    evidence,
    operations,
    optimization,
    science_belief,
    simulation,
    uncertainty,
)
from app.schemas.api import ApiError, ApiMeta
from app.schemas.mission import (
    ComponentSelection,
    DownlinkPlanItem,
    MeasurementRequirement,
    MissionConstraints,
    MissionState,
    ObservationPlanItem,
    OperationsPlan,
    ScienceObjective,
    SpacecraftArchitecture,
    ValidationIssue,
)
from app.schemas.trajectory import Destination, TrajectorySelection
from app.schemas.units import Provenance, Quantity, Uncertainty

T0 = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)


def prov(fidelity: Any = "gameplay-estimate") -> Provenance:
    return Provenance(
        fidelity=fidelity,
        source_name="MISSIONFORGE scenario data",
        source_version="0.1.0",
        retrieved_at=T0,
        published_at=date(2026, 1, 1),
        assumptions=["educational proxy"],
    )


def qty(value: float, unit: Any, fidelity: Any = "derived") -> Quantity:
    return Quantity(value=value, unit=unit, provenance=prov(fidelity))


def uncertainty_() -> Uncertainty:
    return Uncertainty(distribution="triangular", min=0.9, mode=1.0, max=1.2)


# --- mission ---------------------------------------------------------------------------


def measurement() -> MeasurementRequirement:
    return MeasurementRequirement(
        id="meas-albedo",
        description="Global albedo map",
        instrument_capability="visible-imaging",
        target_threshold=qty(2.0, "m", "gameplay-estimate"),
        coverage_weight=1.0,
        required=True,
    )


def mission_state() -> MissionState:
    return MissionState(
        mission_id="mission-001",
        title="NEO Scout",
        scenario_id="neo-rendezvous",
        created_at=T0,
        updated_at=T0,
        design_revision=3,
        science_objectives=[
            ScienceObjective(
                id="obj-surface",
                title="Surface composition",
                question="What is the surface made of?",
                priority=2.0,
                required_measurements=[measurement()],
            )
        ],
        destination=Destination(
            body_id="101955", name="Bennu", body_type="asteroid", source=prov()
        ),
        trajectory=TrajectorySelection(
            provider="scenario-preset",
            option_id="opt-1",
            departure_date=date(2030, 1, 1),
            arrival_date=date(2030, 9, 1),
            time_of_flight_days=243.0,
            mission_delta_v_km_per_s=1.2,
        ),
        architecture=SpacecraftArchitecture(
            launch_vehicle_id="lv-rideshare",
            bus_id="bus-12u",
            propulsion_id="prop-cold-gas",
            power_id="pow-deployable",
            adcs_id="adcs-3axis",
            communications_id="comm-xband",
            thermal_id="th-passive",
            cdh_id="cdh-std",
            instrument_ids=["inst-camera"],
            ground_segment_id="gs-dsn-34m",
        ),
        operations=OperationsPlan(
            mission_duration_days=365.0,
            observation_plan=[
                ObservationPlanItem(
                    measurement_id="meas-albedo",
                    start_day=250.0,
                    duration_hours=4.0,
                    duty_cycle=0.5,
                )
            ],
            downlink_plan=[
                DownlinkPlanItem(
                    start_day=251.0, duration_minutes=60.0, data_rate_bits_per_second=2.0e5
                )
            ],
            safe_mode_policy="balanced",
            autonomy_level="supervised",
        ),
        constraints=MissionConstraints(
            maximum_budget_usd=5.0e7,
            launch_mass_limit_kg=30.0,
            mass_margin_fraction=0.2,
            power_margin_fraction=0.2,
            data_margin_fraction=0.1,
            delta_v_margin_km_per_s=0.05,
        ),
        random_seed=42,
    )


# --- catalog ---------------------------------------------------------------------------


def failure_mode() -> catalog.FailureMode:
    return catalog.FailureMode(
        id="fm-valve-leak",
        description="Valve leak reduces usable propellant",
        base_probability=0.02,
        affected_metric="propellant_mass_kg",
        severity=3,
        mitigation_ids=["mit-redundant-valve"],
    )


def compatibility_rule() -> catalog.CompatibilityRule:
    return catalog.CompatibilityRule(category="bus", ids=["bus-12u"], tags=["cubesat"])


def catalog_component() -> catalog.CatalogComponent:
    return catalog.CatalogComponent(
        id="prop-cold-gas",
        name="Cold-gas thruster module (illustrative)",
        category="propulsion",
        description="Illustrative archetype",
        tags=["cubesat"],
        parameters={"dry_mass": qty(1.2, "kg", "gameplay-estimate")},
        capabilities=["attitude-control"],
        compatible_with=[compatibility_rule()],
        failure_modes=[failure_mode()],
        source_record_id="src-illustrative-001",
        provenance=prov(),
        is_illustrative=True,
    )


# --- analysis --------------------------------------------------------------------------


def suggested_action() -> analysis.SuggestedAction:
    return analysis.SuggestedAction(
        action_id="act-larger-array",
        label="Use a larger solar array",
        expected_effect="+20 W average power",
    )


def constraint_result() -> analysis.ConstraintResult:
    return analysis.ConstraintResult(
        id="power-margin",
        label="Power margin",
        status="warning",
        actual=qty(0.12, "%"),
        limit=qty(0.2, "%"),
        margin_fraction=-0.08,
        severity=2,
        explanation="Average power margin is below the 20 % target.",
        impacted_subsystems=["power"],
        suggested_actions=[suggested_action()],
    )


def budget_analysis() -> analysis.BudgetAnalysis:
    return analysis.BudgetAnalysis(
        dry_mass_kg=qty(20.0, "kg"),
        propellant_mass_kg=qty(2.0, "kg"),
        wet_mass_kg=qty(22.0, "kg"),
        mass_margin_fraction=0.25,
        average_power_w=qty(40.0, "W"),
        peak_power_w=qty(65.0, "W"),
        energy_margin_fraction=0.12,
        data_generated_bits=qty(8.0e9, "bit"),
        data_downlinked_bits=qty(6.0e9, "bit"),
        data_margin_fraction=-0.25,
        required_delta_v_km_per_s=qty(1.2, "km/s"),
        available_delta_v_km_per_s=qty(1.3, "km/s"),
        delta_v_margin_km_per_s=0.1,
        estimated_cost_usd=qty(3.0e7, "USD_2026", "gameplay-estimate"),
    )


def science_analysis() -> analysis.ScienceAnalysis:
    return analysis.ScienceAnalysis(
        coverage_score=72.5,
        weighted_objective_coverage={"obj-surface": 0.725},
        missing_requirements=[],
        collected_fraction=0.9,
        returned_fraction=0.7,
    )


def reliability_analysis() -> analysis.ReliabilityAnalysis:
    return analysis.ReliabilityAnalysis(
        nominal_reliability=0.86, risk_index=0.3, single_point_failures=["comm-xband"]
    )


def score_dimension() -> analysis.ScoreDimension:
    return analysis.ScoreDimension(
        id="scientific-return", weight=30.0, score=21.75, explanation="72.5 % coverage"
    )


def score_breakdown() -> analysis.ScoreBreakdown:
    return analysis.ScoreBreakdown(total=21.75, dimensions=[score_dimension()])


def mission_analysis() -> analysis.MissionAnalysis:
    return analysis.MissionAnalysis(
        mission_id="mission-001",
        design_revision=3,
        engine_version="0.1.0",
        catalog_version="0.1.0",
        calculated_at=T0,
        budgets=budget_analysis(),
        science=science_analysis(),
        reliability=reliability_analysis(),
        constraints=[constraint_result()],
        feasibility="marginal",
        mission_ready=False,
        score=score_breakdown(),
        top_drivers=["data downlink capacity"],
        assumptions=["Science coefficients are educational proxies."],
    )


# --- simulation ------------------------------------------------------------------------


def decision_choice() -> simulation.DecisionChoice:
    return simulation.DecisionChoice(
        id="choice-safe-mode",
        label="Enter safe mode",
        tradeoff="Lose 2 days of science; protect battery",
        effects={"science_days": -2.0, "battery_soc": 0.15},
    )


def mission_event() -> simulation.MissionEvent:
    return simulation.MissionEvent(
        id="evt-0007",
        sequence=7,
        mission_day=260.5,
        phase="science-ops",
        type="decision",
        severity="warning",
        title="Battery approaching reserve",
        description="Eclipse load exceeds generation; state of charge at 32 %.",
        trigger={"channel": "battery_soc", "threshold": 0.3, "rule_id": 4, "scenario": False},
        choices=[decision_choice()],
        resolved_by="choice-safe-mode",
        decision_maker="player",
    )


def telemetry_sample() -> simulation.TelemetrySample:
    return simulation.TelemetrySample(
        channel="battery_soc",
        unit="%",
        mission_day=260.5,
        value=0.32,
        fidelity="gameplay-estimate",
        phase="science-ops",
    )


def decision_record() -> simulation.DecisionRecord:
    return simulation.DecisionRecord(
        event_id="evt-0007",
        choice_id="choice-safe-mode",
        decision_maker="player",
        mission_day=260.5,
        rationale="Protect the battery before the next eclipse.",
    )


def science_outcome() -> simulation.ScienceOutcome:
    return simulation.ScienceOutcome(
        objective_id="obj-surface", collected_fraction=0.9, returned_fraction=0.7, status="partial"
    )


def final_report() -> simulation.FinalReport:
    return simulation.FinalReport(
        outcome="partial",
        summary="Mission returned 70 % of collected science.",
        score=score_breakdown(),
        root_causes=["Downlink capacity below generated data volume"],
        counterfactuals=["A second weekly contact would have returned all data."],
        limitations=["Simplified phase-checkpoint resource model."],
    )


def mission_run() -> simulation.MissionRun:
    return simulation.MissionRun(
        run_id="run-0001",
        mission_id="mission-001",
        design_revision=3,
        seed=42,
        scenario_event_set_id="neo-rendezvous.events@0.1.0",
        engine_version="0.1.0",
        catalog_version="0.1.0",
        experimental=False,
        phases=["pre-launch", "launch-deployment", "science-ops", "complete"],
        events=[mission_event()],
        telemetry=[telemetry_sample()],
        decisions=[decision_record()],
        science_outcomes=[science_outcome()],
        final_report=final_report(),
    )


def simulation_input() -> simulation.SimulationInput:
    return simulation.SimulationInput(
        mission_state=mission_state(),
        analysis=mission_analysis(),
        engine_version="0.1.0",
        catalog_version="0.1.0",
        random_seed=42,
        scenario_event_set_id="neo-rendezvous.events@0.1.0",
        monte_carlo_samples=None,
    )


# --- optimisation / architecture graph -------------------------------------------------


def architecture_node() -> optimization.ArchitectureNode:
    return optimization.ArchitectureNode(
        id="node-inst-camera",
        kind="instrument",
        label="Visible camera",
        entity_id="inst-camera",
        attributes={"mass_kg": 1.1, "count": 1, "enabled": True, "band": "visible"},
    )


def architecture_edge() -> optimization.ArchitectureEdge:
    return optimization.ArchitectureEdge(
        id="edge-1",
        from_id="node-inst-camera",
        to_id="node-meas-albedo",
        kind="satisfies",
        rationale="Camera provides visible-imaging capability",
    )


def optimization_objective() -> optimization.OptimizationObjective:
    return optimization.OptimizationObjective(
        key="lifecycle_cost", direction="minimize", weight=None
    )


def architecture_candidate() -> optimization.ArchitectureCandidate:
    return optimization.ArchitectureCandidate(
        id="cand-000",
        mission_state=mission_state(),
        analysis=mission_analysis(),
        objective_vector={"lifecycle_cost": 3.0e7, "negative_science_return": -72.5},
        feasible=True,
        generation=0,
        explanation=["Baseline design"],
    )


def trade_alternative() -> optimization.TradeAlternative:
    return optimization.TradeAlternative(
        analysis=mission_analysis(), deltas={"dry_mass_kg": -1.5, "science_score": 4.0}
    )


def trade_study_result() -> optimization.TradeStudyResult:
    return optimization.TradeStudyResult(
        base_analysis=mission_analysis(), alternatives=[trade_alternative()]
    )


def optimization_result() -> optimization.OptimizationResult:
    return optimization.OptimizationResult(
        seed=42,
        objectives=[optimization_objective()],
        candidates=[architecture_candidate()],
        pareto_front_ids=["cand-000"],
        archetypes={"lean": "cand-000", "science-max": "cand-000", "resilient": "cand-000"},
        near_misses=[],
    )


# --- uncertainty -----------------------------------------------------------------------


def distribution_spec() -> uncertainty.DistributionSpec:
    return uncertainty.DistributionSpec(kind="triangular", min=0.9, mode=1.0, max=1.1)


def uncertain_parameter() -> uncertainty.UncertainParameter:
    return uncertainty.UncertainParameter(
        id="up-isp",
        path="propulsion.isp_scale",
        kind="aleatory",
        distribution=distribution_spec(),
        rationale="Propulsion performance dispersion (gameplay estimate)",
        source_ref=None,
    )


def uncertainty_profile() -> uncertainty.UncertaintyProfile:
    return uncertainty.UncertaintyProfile(
        id="default", version="0.1.0", parameters=[uncertain_parameter()]
    )


def metric_quantiles() -> uncertainty.MetricQuantiles:
    return uncertainty.MetricQuantiles(p10=60.0, median=70.0, p90=78.0, unit="score")


def robustness_result() -> uncertainty.RobustnessResult:
    return uncertainty.RobustnessResult(
        samples=250,
        seed=42,
        probability_feasible=0.8,
        feasibility_wilson_95=(0.746, 0.844),
        metrics={"returned_science": metric_quantiles()},
        failure_counts={"power-margin": 50},
        profile_version="0.1.0",
        assumptions=["Distribution widths are gameplay estimates."],
        disclaimer="Monte Carlo robustness proxy; not a flight-qualified PRA.",
    )


# --- science belief --------------------------------------------------------------------


def science_hypothesis() -> science_belief.ScienceHypothesis:
    return science_belief.ScienceHypothesis(
        id="hyp-volatile",
        label="Volatile-rich surface",
        prior_probability=0.4,
        description="Illustrative scenario label, not a claim about the real body.",
    )


def observation_likelihood() -> science_belief.ObservationLikelihood:
    return science_belief.ObservationLikelihood(
        instrument_id="inst-camera",
        outcome_id="dark-albedo",
        likelihood_by_hypothesis={"hyp-volatile": 0.7, "hyp-silicate": 0.2},
    )


def hypothesis_probability() -> science_belief.HypothesisProbability:
    return science_belief.HypothesisProbability(hypothesis_id="hyp-volatile", probability=0.4)


def observation_record() -> science_belief.ObservationRecord:
    return science_belief.ObservationRecord(
        task_id="obs-1", outcome_id="dark-albedo", timestamp_mission_seconds=2.2e7
    )


def belief_state() -> science_belief.BeliefState:
    return science_belief.BeliefState(
        hypotheses=[
            science_belief.HypothesisProbability(hypothesis_id="hyp-volatile", probability=0.5),
            science_belief.HypothesisProbability(hypothesis_id="hyp-silicate", probability=0.5),
        ],
        observation_history=[observation_record()],
        entropy_bits=1.0,
        version=1,
    )


# --- operations ------------------------------------------------------------------------


def observation_opportunity() -> operations.ObservationOpportunity:
    return operations.ObservationOpportunity(
        id="opp-1",
        start=1000.0,
        end=1600.0,
        instrument_id="inst-camera",
        expected_science_value=5.0,
        generated_data_bits=4.0e8,
        energy_joules=3.6e4,
        slew_seconds=120.0,
        compatible_attitude="nadir",
    )


def contact_window() -> operations.ContactWindow:
    return operations.ContactWindow(
        id="cw-1",
        start=2000.0,
        end=5600.0,
        max_downlink_bits=7.2e8,
        station_id="gs-dsn-34m",
        link_margin_db=3.1,
    )


def scheduled_data_cycle() -> operations.ScheduledDataCycle:
    return operations.ScheduledDataCycle(
        id="cycle-1",
        observations=["opp-1"],
        contact_window_id="cw-1",
        buffer_before_bits=0.0,
        buffer_after_bits=0.0,
        explanation="Observation fully downlinked during cw-1.",
    )


def rejected_opportunity() -> operations.RejectedOpportunity:
    return operations.RejectedOpportunity(id="opp-2", reason_code="BUFFER_OVERFLOW_BEFORE_CONTACT")


def buffer_point() -> operations.BufferPoint:
    return operations.BufferPoint(t=1600.0, bits=4.0e8)


def mission_schedule() -> operations.MissionSchedule:
    return operations.MissionSchedule(
        accepted=["opp-1"],
        rejected=[rejected_opportunity()],
        cycles=[scheduled_data_cycle()],
        buffer_timeline=[buffer_point()],
    )


def autonomy_action() -> operations.AutonomyAction:
    return operations.AutonomyAction(
        id="act-1",
        observation_id="opp-1",
        expected_science_value=5.0,
        energy_joules=3.6e4,
        data_bits=4.0e8,
        risk=0.1,
        slew_seconds=120.0,
    )


def scored_action() -> operations.ScoredAction:
    return operations.ScoredAction(
        action_id="act-1", utility=3.2, feasible=True, rejection_reason=None
    )


def autonomy_decision() -> operations.AutonomyDecision:
    return operations.AutonomyDecision(
        decision_maker="onboard-policy",
        policy="resource-aware",
        candidates=[
            scored_action(),
            operations.ScoredAction(
                action_id="act-2", utility=4.0, feasible=False, rejection_reason="ENERGY"
            ),
        ],
        selected_action_id="act-1",
        reason="Highest utility among feasible actions.",
    )


# --- evidence --------------------------------------------------------------------------


def evidence_record() -> evidence.EvidenceRecord:
    return evidence.EvidenceRecord(
        id="ev-1",
        subject_id="analysis.budgets.dryMassKg",
        fidelity="derived",
        source_title="MISSIONFORGE mass model",
        source_url=None,
        source_version="engine 0.1.0",
        retrieved_at=None,
        published_at=None,
        unit="kg",
        conversion_notes="None; native SI.",
        assumptions=["10 % structure allocation"],
        limitations=["Educational proxy"],
        related_ids=["power-margin"],
    )


def mission_run_manifest() -> evidence.MissionRunManifest:
    return evidence.MissionRunManifest(
        schema_version="1.0",
        engine_version="0.1.0",
        catalog_version="0.1.0",
        scenario_version="0.1.0",
        event_set_id="neo-rendezvous.events@0.1.0",
        seed=42,
        app_version="0.1.0",
    )


def mission_package_manifest() -> evidence.MissionPackageManifest:
    return evidence.MissionPackageManifest(
        app_version="0.1.0",
        engine_version="0.1.0",
        catalog_version="0.1.0",
        scenario_version="0.1.0",
    )


def mission_package() -> evidence.MissionPackage:
    return evidence.MissionPackage(
        exported_at=T0,
        mission=mission_state(),
        latest_analysis=mission_analysis(),
        runs=[mission_run()],
        evidence=[evidence_record()],
        manifest=mission_package_manifest(),
    )


# --- registry --------------------------------------------------------------------------

BUILDERS: dict[str, Callable[[], BaseModel]] = {
    "mission.MissionState": mission_state,
    "mission.MeasurementRequirement": measurement,
    "mission.ComponentSelection": lambda: ComponentSelection(
        component_id="inst-camera", quantity=1, enabled=True, overrides={"duty": 0.5}
    ),
    "mission.ValidationIssue": lambda: ValidationIssue(code="X", path="p", message="m"),
    "mission.ScienceObjective": lambda: mission_state().science_objectives[0],
    "mission.SpacecraftArchitecture": lambda: mission_state().architecture,
    "mission.ObservationPlanItem": lambda: mission_state().operations.observation_plan[0],
    "mission.DownlinkPlanItem": lambda: mission_state().operations.downlink_plan[0],
    "mission.OperationsPlan": lambda: mission_state().operations,
    "mission.MissionConstraints": lambda: mission_state().constraints,
    "trajectory.Destination": lambda: mission_state().destination,
    "trajectory.TrajectorySelection": lambda: mission_state().trajectory,
    "units.Provenance": prov,
    "units.Uncertainty": uncertainty_,
    "units.Quantity": lambda: Quantity(
        value=1.0, unit="kg", provenance=prov(), uncertainty=uncertainty_()
    ),
    "api.ApiMeta": lambda: ApiMeta(request_id="req-1", generated_at=T0, source_status="demo"),
    "api.ApiError": lambda: ApiError(
        code="VALIDATION_ERROR", message="bad", retryable=False, details={"path": "title"}
    ),
    "catalog.FailureMode": failure_mode,
    "catalog.CompatibilityRule": compatibility_rule,
    "catalog.CatalogComponent": catalog_component,
    "analysis.SuggestedAction": suggested_action,
    "analysis.ConstraintResult": constraint_result,
    "analysis.BudgetAnalysis": budget_analysis,
    "analysis.ScienceAnalysis": science_analysis,
    "analysis.ReliabilityAnalysis": reliability_analysis,
    "analysis.ScoreDimension": score_dimension,
    "analysis.ScoreBreakdown": score_breakdown,
    "analysis.MissionAnalysis": mission_analysis,
    "simulation.DecisionChoice": decision_choice,
    "simulation.MissionEvent": mission_event,
    "simulation.TelemetrySample": telemetry_sample,
    "simulation.DecisionRecord": decision_record,
    "simulation.ScienceOutcome": science_outcome,
    "simulation.FinalReport": final_report,
    "simulation.MissionRun": mission_run,
    "simulation.SimulationInput": simulation_input,
    "optimization.ArchitectureNode": architecture_node,
    "optimization.ArchitectureEdge": architecture_edge,
    "optimization.OptimizationObjective": optimization_objective,
    "optimization.ArchitectureCandidate": architecture_candidate,
    "optimization.TradeAlternative": trade_alternative,
    "optimization.TradeStudyResult": trade_study_result,
    "optimization.OptimizationResult": optimization_result,
    "uncertainty.DistributionSpec": distribution_spec,
    "uncertainty.UncertainParameter": uncertain_parameter,
    "uncertainty.UncertaintyProfile": uncertainty_profile,
    "uncertainty.MetricQuantiles": metric_quantiles,
    "uncertainty.RobustnessResult": robustness_result,
    "science_belief.ScienceHypothesis": science_hypothesis,
    "science_belief.ObservationLikelihood": observation_likelihood,
    "science_belief.HypothesisProbability": hypothesis_probability,
    "science_belief.ObservationRecord": observation_record,
    "science_belief.BeliefState": belief_state,
    "operations.ObservationOpportunity": observation_opportunity,
    "operations.ContactWindow": contact_window,
    "operations.ScheduledDataCycle": scheduled_data_cycle,
    "operations.RejectedOpportunity": rejected_opportunity,
    "operations.BufferPoint": buffer_point,
    "operations.MissionSchedule": mission_schedule,
    "operations.AutonomyAction": autonomy_action,
    "operations.ScoredAction": scored_action,
    "operations.AutonomyDecision": autonomy_decision,
    "evidence.EvidenceRecord": evidence_record,
    "evidence.MissionRunManifest": mission_run_manifest,
    "evidence.MissionPackageManifest": mission_package_manifest,
    "evidence.MissionPackage": mission_package,
}


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "contract_name" in metafunc.fixturenames:
        metafunc.parametrize("contract_name", sorted(BUILDERS))


@pytest.fixture
def builders() -> dict[str, Callable[[], BaseModel]]:
    return BUILDERS

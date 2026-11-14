"""Blackout autonomy inside a mission run (Task 6.5, Phase 4 <-> 6 join).

Walks the planned observations in time order. At each one the command authority comes
from the flown contact windows: in contact the ground team commands it; otherwise the
onboard policy (``POLICY_FOR_SAFE_MODE[safe_mode_policy]``, ruling R44) decides between
observing with the engine's assigned instrument and holding. Every decision is logged with
its input belief, candidate utilities, selection and reason. An executed observation with
a science model updates the belief with a seeded simulated outcome (19.4); a held
observation is removed from the as-flown plan, so the engine re-analyses the science.

Scope limits (labelled in the run): one candidate per plan slot (the engine's assigned
instrument) plus "hold"; the hidden scenario truth never leaves the server; scenarios
without a hypothesis model log an empty belief (EIG = 0).
"""

from collections.abc import Mapping
from dataclasses import dataclass

from app.domain.analysis.context import AnalysisContext
from app.domain.analysis.orchestrator import _assign_instruments
from app.domain.catalog.loader import Catalog
from app.domain.catalog.resolver import resolve_architecture
from app.domain.operations.plan_autonomy import (
    POLICY_FOR_SAFE_MODE,
    OnboardResources,
    action_risk,
    command_authority,
    plan_autonomy,
)
from app.domain.operations.schedule_inputs import DAY_S, build_schedule_inputs
from app.domain.science_belief import (
    ScienceModel,
    draw_outcome,
    expected_information_gain,
    initial_belief,
    update_belief,
)
from app.domain.simulation.decisions import buffer_bits_at
from app.schemas.analysis import MissionAnalysis
from app.schemas.mission import MissionState
from app.schemas.operations import AutonomyAction, AutonomyDecision, ContactWindow
from app.schemas.science_belief import BeliefState

AUTONOMY_LIMITATION = (
    "Blackout autonomy is a one-step policy selector over the planned observations "
    "(observe with the assigned instrument or hold), scored with gameplay-estimate weights; "
    "it is not a POMDP planner or flight software."
)


@dataclass(frozen=True)
class AutonomyOutcome:
    log: tuple[AutonomyDecision, ...]
    held: Mapping[int, str]  # planned observation index -> reason it was held onboard
    final_belief: BeliefState | None


def _empty_belief() -> BeliefState:
    return BeliefState(hypotheses=(), observation_history=(), entropy_bits=0.0, version=0)


def run_autonomy(
    state: MissionState,
    analysis: MissionAnalysis,
    catalog: Catalog,
    ctx: AnalysisContext,
    contacts_state: MissionState,
    *,
    science_model: ScienceModel | None,
    seed: int,
    end_day: float | None = None,
) -> AutonomyOutcome:
    """``contacts_state`` carries the flown downlink plan (missed contacts removed)."""
    policy = POLICY_FOR_SAFE_MODE[state.operations.safe_mode_policy]
    inputs = build_schedule_inputs(state, analysis, catalog)
    contacts: list[ContactWindow] = build_schedule_inputs(
        contacts_state, analysis, catalog
    ).contacts
    assigned = {
        mid: comp.id
        for mid, comp in _assign_instruments(
            state, resolve_architecture(state.architecture, catalog)
        ).items()
    }
    thermal = next((c for c in analysis.constraints if c.id == "thermal"), None)
    thermal_ok = thermal is None or thermal.status != "fail"
    belief = initial_belief(science_model) if science_model is not None else _empty_belief()
    uses: dict[str, int] = {}
    log: list[AutonomyDecision] = []
    held: dict[int, str] = {}

    by_slot: dict[int, list[str]] = {}
    for opp in inputs.opportunities:
        by_slot.setdefault(int(opp.id.split(":")[1]), []).append(opp.id)
    opp_by_id = {o.id: o for o in inputs.opportunities}

    for idx, item in enumerate(state.operations.observation_plan):
        if end_day is not None and item.start_day >= end_day:
            break
        inst = assigned.get(item.measurement_id)
        slot = [opp_by_id[i] for i in by_slot.get(idx, []) if opp_by_id[i].instrument_id == inst]
        if not slot:
            continue
        t = item.start_day * DAY_S
        resources = OnboardResources(
            energy_budget_joules=inputs.resources.max_energy_per_observation_joules,
            free_buffer_bits=max(
                0.0, ctx.buffer_capacity_bits - buffer_bits_at(ctx, item.start_day)
            ),
            buffer_capacity_bits=ctx.buffer_capacity_bits,
            supported_attitudes=inputs.resources.supported_attitudes,
            thermal_ok=thermal_ok,
        )
        actions, info, attitude = [], {}, {}
        for o in slot:
            aid = f"observe:{idx}:{o.instrument_id}"
            tables = science_model.tables(o.instrument_id) if science_model else []
            info[aid] = expected_information_gain(belief, tables) if tables else 0.0
            attitude[aid] = o.compatible_attitude
            actions.append(
                AutonomyAction(
                    id=aid,
                    observation_id=o.id,
                    expected_science_value=o.expected_science_value,
                    energy_joules=o.energy_joules,
                    data_bits=o.generated_data_bits,
                    risk=action_risk(o.energy_joules, o.generated_data_bits, resources),
                    slew_seconds=o.slew_seconds,
                )
            )
        maker = command_authority(t, contacts)
        decision = plan_autonomy(
            policy,
            decision_maker=maker,
            belief=belief,
            actions=actions,
            information_bits=info,
            attitude=attitude,
            resources=resources,
            context=f"Day {item.start_day:g}, {item.measurement_id}:",
        )
        log.append(decision)
        chosen = next((a for a in actions if a.id == decision.selected_action_id), None)
        if chosen is None:
            held[idx] = decision.reason
            continue
        inst_id = chosen.id.split(":", 2)[2]
        if science_model is not None and science_model.tables(inst_id):
            n = uses.get(inst_id, 0)
            uses[inst_id] = n + 1
            outcome = draw_outcome(science_model, seed, inst_id, n)
            belief = update_belief(
                belief,
                science_model.table(inst_id, outcome),
                task_id=chosen.id,
                timestamp_mission_seconds=t,
            )
    return AutonomyOutcome(
        log=tuple(log),
        held=held,
        final_belief=belief if science_model is not None else None,
    )


__all__ = ["AUTONOMY_LIMITATION", "AutonomyOutcome", "run_autonomy"]

"""Explainable deterministic onboard policy selection."""

from collections.abc import Sequence

from app.schemas.operations import (
    AutonomyAction,
    AutonomyDecision,
    AutonomyPolicy,
    ScoredAction,
)
from app.schemas.science_belief import BeliefState


def choose_autonomy_action(
    belief: BeliefState,
    actions: Sequence[AutonomyAction],
    *,
    policy: AutonomyPolicy,
    blackout: bool,
    available_energy_joules: float,
    available_storage_bits: float,
) -> AutonomyDecision:
    """Choose one feasible action; blackout always forces onboard authority."""
    if blackout:
        decision_maker = "onboard-policy"
    else:
        decision_maker = "ground"
    scored: list[ScoredAction] = []
    for action in actions:
        if action.energy_joules > available_energy_joules:
            scored.append(
                ScoredAction(
                    action_id=action.id,
                    utility=0.0,
                    feasible=False,
                    rejection_reason="ENERGY",
                )
            )
            continue
        if action.data_bits > available_storage_bits:
            scored.append(
                ScoredAction(
                    action_id=action.id,
                    utility=0.0,
                    feasible=False,
                    rejection_reason="STORAGE",
                )
            )
            continue
        resource_penalty = action.energy_joules / max(available_energy_joules, 1.0)
        if policy == "conservative":
            utility = action.expected_science_value - action.risk * 2.0 - resource_penalty
        elif policy == "science-first":
            utility = action.expected_science_value * 2.0 - action.risk - resource_penalty
        else:
            utility = action.expected_science_value - action.risk - resource_penalty
        scored.append(ScoredAction(action_id=action.id, utility=utility, feasible=True))

    feasible = [item for item in scored if item.feasible]
    selected = max(feasible, key=lambda item: (item.utility, item.action_id)) if feasible else None
    reason = (
        "Blackout: ground commands are unavailable; selected the highest-utility "
        "feasible onboard action."
        if blackout and selected
        else "Ground selected the highest-utility feasible action."
        if selected
        else "No candidate action satisfies the available energy and storage constraints."
    )
    return AutonomyDecision(
        decision_maker=decision_maker,
        policy=policy,
        belief=belief,
        candidates=tuple(scored),
        selected_action_id=selected.action_id if selected else None,
        reason=reason,
    )

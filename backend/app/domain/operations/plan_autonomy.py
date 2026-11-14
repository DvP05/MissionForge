"""Onboard autonomy and communication-blackout authority (architecture 19.5, Task 6.5).

A finite, explainable policy selector, not a POMDP solver. During a blackout (no planned
ground contact is in progress) ground commands are rejected and the onboard policy decides
each planned observation: it scores the candidate actions with the 19.4 utility

    utility = w_s*value + w_i*EIG - w_e*energy - w_d*data - w_r*risk - w_slew*slew

(energy and data as fractions of the onboard budget, slew in hours), rejects any action
that breaks a hard limit (battery reserve, free storage, pointing, thermal, slew), and
picks the highest utility; ties go to the lower action id. "Hold" (no action) is chosen
when nothing is feasible or nothing has positive utility. All weights are
gameplay-estimates. Deterministic: same inputs, same choice.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.domain.errors import DomainValidationError
from app.schemas.operations import (
    AutonomyAction,
    AutonomyDecision,
    AutonomyPolicy,
    ContactWindow,
    ScoredAction,
)
from app.schemas.science_belief import BeliefState

MAX_CANDIDATES = 10
SLEW_HOUR_S = 3600.0

DecisionMakerLabel = str  # "ground" | "onboard-policy"


@dataclass(frozen=True)
class AutonomyWeights:
    science: float
    information: float
    energy: float
    data: float
    risk: float
    slew: float
    reserve_fraction: float  # battery share the policy keeps untouched (hard limit)
    min_information_bits: float  # policy rule: skip observations expected to teach less
    summary: str


# gameplay-estimate weights, one per architecture 19.5 policy (decision D3 names).
POLICY_WEIGHTS: dict[AutonomyPolicy, AutonomyWeights] = {
    "conservative": AutonomyWeights(
        1.0, 0.5, 2.0, 1.0, 3.0, 1.0, 0.4, 0.25,
        "Protect power, storage and health; skip low-information observations.",
    ),
    "science-first": AutonomyWeights(
        1.0, 2.0, 0.2, 0.1, 0.5, 0.2, 0.1, 0.0,
        "Take the feasible observation with the most science value and information gain.",
    ),
    "resource-aware": AutonomyWeights(
        1.0, 1.0, 1.0, 1.0, 1.0, 0.5, 0.25, 0.0,
        "Most science per constrained resource while keeping a 25% battery reserve.",
    ),
}  # fmt: skip

# MissionState.operations.safe_mode_policy -> autonomy policy (ruling R44).
POLICY_FOR_SAFE_MODE: dict[str, AutonomyPolicy] = {
    "conservative": "conservative",
    "balanced": "resource-aware",
    "aggressive": "science-first",
}


class GroundCommandRejected(DomainValidationError):  # noqa: N818 - name fixed by the plan
    def __init__(self, t: float, next_contact: float | None) -> None:
        when = (
            f"the next contact opens at mission second {next_contact:g}"
            if next_contact is not None
            else "no further contact is planned"
        )
        super().__init__(
            "GROUND_COMMAND_REJECTED",
            "command",
            f"communication blackout at mission second {t:g}: ground cannot command the "
            f"spacecraft; {when}.",
        )
        self.next_contact = next_contact


def in_contact(t: float, contacts: Sequence[ContactWindow]) -> bool:
    return any(c.start <= t <= c.end for c in contacts)


def next_contact_start(t: float, contacts: Sequence[ContactWindow]) -> float | None:
    upcoming = [c.start for c in contacts if c.start > t]
    return min(upcoming) if upcoming else None


def command_authority(t: float, contacts: Sequence[ContactWindow]) -> DecisionMakerLabel:
    return "ground" if in_contact(t, contacts) else "onboard-policy"


def apply_ground_command(t: float, contacts: Sequence[ContactWindow]) -> None:
    """Accept a ground command at mission second ``t`` or raise during a blackout."""
    if not in_contact(t, contacts):
        raise GroundCommandRejected(t, next_contact_start(t, contacts))


@dataclass(frozen=True)
class OnboardResources:
    energy_budget_joules: float  # usable battery energy for one observation
    free_buffer_bits: float  # storage free at decision time (engine data ledger)
    buffer_capacity_bits: float
    supported_attitudes: frozenset[str]
    thermal_ok: bool
    max_slew_seconds: float = 1800.0  # gameplay-estimate


def _frac(x: float, budget: float) -> float:
    return x / budget if budget > 0 else (0.0 if x <= 0 else math.inf)


def score_actions(
    actions: Sequence[AutonomyAction],
    information_bits: Mapping[str, float],
    attitude: Mapping[str, str],
    resources: OnboardResources,
    weights: AutonomyWeights,
    *,
    apply_policy_rules: bool = True,
) -> list[ScoredAction]:
    """Utility of each action (at most MAX_CANDIDATES, by id) and why it is infeasible.

    ``apply_policy_rules=False`` keeps only the hard limits (a ground team commanding in
    contact is not bound by the onboard policy's information threshold).
    """
    out: list[ScoredAction] = []
    for a in sorted(actions, key=lambda x: x.id)[:MAX_CANDIDATES]:
        eig = information_bits.get(a.id, 0.0)
        energy = _frac(a.energy_joules, resources.energy_budget_joules)
        data = _frac(a.data_bits, resources.buffer_capacity_bits)
        utility = (
            weights.science * a.expected_science_value
            + weights.information * eig
            - weights.energy * min(energy, 10.0)
            - weights.data * min(data, 10.0)
            - weights.risk * a.risk
            - weights.slew * a.slew_seconds / SLEW_HOUR_S
        )
        reason: str | None = None
        if attitude.get(a.id, "") not in resources.supported_attitudes:
            reason = "POINTING: needs finer pointing than the ADCS provides"
        elif not resources.thermal_ok:
            reason = "THERMAL: the design's thermal check fails"
        elif a.energy_joules > resources.energy_budget_joules * (1 - weights.reserve_fraction):
            reason = f"ENERGY: would dip into the {weights.reserve_fraction:.0%} battery reserve"
        elif a.data_bits > resources.free_buffer_bits:
            reason = "STORAGE: not enough free storage before the next downlink"
        elif a.slew_seconds > resources.max_slew_seconds:
            reason = "SLEW: the slew does not fit the observation window"
        elif apply_policy_rules and eig < weights.min_information_bits:
            reason = (
                f"LOW_INFORMATION: expected gain {eig:.2f} bits is below this policy's "
                f"{weights.min_information_bits:.2f}-bit threshold"
            )
        out.append(
            ScoredAction(
                action_id=a.id,
                utility=utility,
                feasible=reason is None,
                rejection_reason=reason,
            )
        )
    return out


def action_risk(energy_joules: float, data_bits: float, resources: OnboardResources) -> float:
    """gameplay-estimate operational risk in [0, 1]: how close the action drives the
    battery or the free storage to its limit."""
    e = _frac(energy_joules, resources.energy_budget_joules)
    d = _frac(data_bits, resources.free_buffer_bits)
    return min(1.0, max(e, d))


def plan_autonomy(
    policy: AutonomyPolicy,
    *,
    decision_maker: DecisionMakerLabel,
    belief: BeliefState,
    actions: Sequence[AutonomyAction],
    information_bits: Mapping[str, float],
    attitude: Mapping[str, str],
    resources: OnboardResources,
    context: str = "",
) -> AutonomyDecision:
    """One decision. Onboard: the policy decides. Ground (in contact): hard limits only."""
    weights = POLICY_WEIGHTS[policy]
    onboard = decision_maker == "onboard-policy"
    scored = score_actions(
        actions, information_bits, attitude, resources, weights, apply_policy_rules=onboard
    )
    best = min(
        (s for s in scored if s.feasible and s.utility > 0.0),
        key=lambda s: (-s.utility, s.action_id),
        default=None,
    )
    prefix = f"{context} " if context else ""
    if best is not None:
        runner_up = [s for s in scored if s.feasible and s is not best]
        why = f"highest utility {best.utility:.2f}"
        if runner_up:
            why += f" (next {max(s.utility for s in runner_up):.2f})"
        who = (
            f"Onboard {policy} policy during blackout selects {best.action_id}: {why}."
            if onboard
            else f"Ground contact: the ground team commands {best.action_id} ({why})."
        )
        reason = prefix + who
    else:
        blocked = "; ".join(
            f"{s.action_id}: {s.rejection_reason or f'utility {s.utility:.2f} <= 0'}"
            for s in scored
        )
        who = "Onboard" if onboard else "Ground"
        reason = prefix + f"{who} holds (no observation): {blocked or 'no candidate actions'}."
    return AutonomyDecision(
        decision_maker="onboard-policy" if onboard else "ground",
        policy=policy,
        belief=belief,
        candidates=tuple(scored),
        selected_action_id=best.action_id if best is not None else None,
        reason=reason,
    )


__all__ = [
    "MAX_CANDIDATES",
    "POLICY_FOR_SAFE_MODE",
    "POLICY_WEIGHTS",
    "AutonomyWeights",
    "GroundCommandRejected",
    "OnboardResources",
    "action_risk",
    "apply_ground_command",
    "command_authority",
    "in_contact",
    "next_contact_start",
    "plan_autonomy",
    "score_actions",
]

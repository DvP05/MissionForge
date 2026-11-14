"""Onboard autonomy + blackout authority (Task 6.5, architecture 19.5, AC-19)."""

import pytest

from app.domain.operations.plan_autonomy import (
    MAX_CANDIDATES,
    POLICY_WEIGHTS,
    GroundCommandRejected,
    OnboardResources,
    apply_ground_command,
    command_authority,
    plan_autonomy,
    score_actions,
)
from app.schemas.operations import AutonomyAction, ContactWindow
from app.schemas.science_belief import BeliefState, HypothesisProbability

CONTACTS = [
    ContactWindow(id="c0", start=100.0, end=200.0, max_downlink_bits=1e9, station_id="g",
                  link_margin_db=3.0),
    ContactWindow(id="c1", start=500.0, end=600.0, max_downlink_bits=1e9, station_id="g",
                  link_margin_db=3.0),
]  # fmt: skip
BELIEF = BeliefState(
    hypotheses=(
        HypothesisProbability(hypothesis_id="a", probability=0.5),
        HypothesisProbability(hypothesis_id="b", probability=0.5),
    ),
    observation_history=(),
    entropy_bits=1.0,
    version=0,
)
RES = OnboardResources(
    energy_budget_joules=1000.0,
    free_buffer_bits=1e6,
    buffer_capacity_bits=2e6,
    supported_attitudes=frozenset({"target-pointing"}),
    thermal_ok=True,
)


def _a(aid: str, *, value: float = 1.0, energy: float = 100.0, data: float = 1e5) -> AutonomyAction:
    return AutonomyAction(
        id=aid, observation_id=f"obs-{aid}", expected_science_value=value,
        energy_joules=energy, data_bits=data, risk=0.1, slew_seconds=0.0,
    )  # fmt: skip


def _plan(
    actions, *, policy="resource-aware", maker="onboard-policy", info=None, res=RES, attitude=None
):  # type: ignore[no-untyped-def]
    return plan_autonomy(
        policy, decision_maker=maker, belief=BELIEF, actions=actions,
        information_bits=info or {}, resources=res,
        attitude=attitude or {a.id: "target-pointing" for a in actions},
    )  # fmt: skip


def test_ground_command_rejected_in_blackout_and_allowed_in_contact() -> None:
    with pytest.raises(GroundCommandRejected) as err:
        apply_ground_command(300.0, CONTACTS)
    assert err.value.code == "GROUND_COMMAND_REJECTED" and err.value.next_contact == 500.0
    apply_ground_command(150.0, CONTACTS)  # in contact: replanning allowed
    apply_ground_command(550.0, CONTACTS)  # after the next contact opens
    assert command_authority(300.0, CONTACTS) == "onboard-policy"
    assert command_authority(150.0, CONTACTS) == "ground"


@pytest.mark.parametrize(
    ("breach", "code"),
    [
        ({"res": OnboardResources(1000.0, 1e6, 2e6, frozenset({"target-pointing"}), True)},
         None),
        ({"energy": 900.0}, "ENERGY"),
        ({"data": 5e6}, "STORAGE"),
        ({"attitude": "precision-pointing"}, "POINTING"),
        ({"res": OnboardResources(1000.0, 1e6, 2e6, frozenset({"target-pointing"}), False)},
         "THERMAL"),
    ],
)  # fmt: skip
def test_hard_limit_breaches_are_never_selected(
    breach: dict[str, object], code: str | None
) -> None:
    bad = _a("bad", value=5.0, energy=float(breach.get("energy", 100.0)),  # type: ignore[arg-type]
             data=float(breach.get("data", 1e5)))  # type: ignore[arg-type]  # fmt: skip
    res = breach.get("res", RES)
    att = {"bad": str(breach.get("attitude", "target-pointing"))}
    d = _plan([bad], res=res, attitude=att)  # type: ignore[arg-type]
    if code is None:
        assert d.selected_action_id == "bad"
    else:
        assert d.selected_action_id is None
        assert d.candidates[0].rejection_reason is not None
        assert d.candidates[0].rejection_reason.startswith(code)


def test_ground_in_contact_is_bound_by_hard_limits_too() -> None:
    d = _plan([_a("x", energy=5000.0)], maker="ground")
    assert d.decision_maker == "ground" and d.selected_action_id is None


def test_blackout_decision_is_logged_with_inputs_utilities_selection_and_reason() -> None:
    d = _plan([_a("x", value=1.0), _a("y", value=2.0)])
    assert d.decision_maker == "onboard-policy"
    assert d.belief == BELIEF
    assert [c.action_id for c in d.candidates] == ["x", "y"]
    assert all(isinstance(c.utility, float) for c in d.candidates)
    assert d.selected_action_id == "y"
    assert "blackout" in d.reason and "y" in d.reason


def test_same_inputs_same_choice_and_ties_break_by_id() -> None:
    acts = [_a("b"), _a("a")]
    first = _plan(acts)
    assert first == _plan(list(reversed(acts)))
    assert first.selected_action_id == "a"


def test_at_most_ten_candidates_are_considered() -> None:
    acts = [_a(f"a{i:02d}") for i in range(15)]
    d = _plan(acts)
    assert len(d.candidates) == MAX_CANDIDATES == 10
    scored = score_actions(acts, {}, {a.id: "target-pointing" for a in acts}, RES,
                           POLICY_WEIGHTS["science-first"])  # fmt: skip
    assert len(scored) == 10


def test_conservative_skips_low_information_observation_science_first_takes() -> None:
    low = _a("low", value=1.0)
    info = {"low": 0.05}
    assert _plan([low], policy="science-first", info=info).selected_action_id == "low"
    cons = _plan([low], policy="conservative", info=info)
    assert cons.selected_action_id is None
    assert "LOW_INFORMATION" in cons.reason


def test_information_gain_raises_utility() -> None:
    plain = _plan([_a("x")], info={"x": 0.0}).candidates[0].utility
    rich = _plan([_a("x")], info={"x": 1.0}).candidates[0].utility
    assert rich > plain

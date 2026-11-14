"""Phase schedule derived from the trajectory and operations plan (Task 4.1)."""

import pytest

from app.domain.simulation.phases import SIM_PHASES, build_schedule
from app.schemas.mission import MissionState
from tests.unit.simulation.conftest import make_state


def _with_ops(state: MissionState, **ops: object) -> MissionState:
    dump = state.model_dump()
    dump["operations"] = {**dump["operations"], **ops}
    return MissionState.model_validate(dump)


def test_phase_order_is_exact() -> None:
    assert SIM_PHASES == (
        "launch-deployment",
        "commissioning",
        "cruise",
        "mid-course",
        "approach",
        "science-ops",
        "downlink-return",
    )


def test_neo_schedule_days() -> None:
    s = build_schedule(make_state())
    days = dict(s.transitions)
    assert [p for p, _ in s.transitions] == [*SIM_PHASES, "complete"]
    assert days["launch-deployment"] == 0.0
    assert days["commissioning"] == 1.0  # launch gameplay default 1 d
    assert days["cruise"] == 15.0  # + commissioning gameplay default 14 d
    assert days["approach"] == 245.0  # arrival (time of flight 275 d) - 30 d approach
    assert days["mid-course"] == pytest.approx(130.0)  # midpoint of cruise..approach
    assert days["science-ops"] == 290.0  # first observation
    assert days["downlink-return"] == pytest.approx(320.0 + 8.0 / 24.0)  # last obs end
    assert days["complete"] == 420.0  # mission duration
    assert s.arrival_day == 275.0


def test_phase_at_boundaries_belong_to_new_phase() -> None:
    s = build_schedule(make_state())
    assert s.phase_at(0.0) == "launch-deployment"
    assert s.phase_at(14.99) == "commissioning"
    assert s.phase_at(15.0) == "cruise"
    assert s.phase_at(300.0) == "science-ops"
    assert s.phase_at(420.0) == "complete"


@pytest.mark.parametrize("scenario", ["neo-rendezvous", "lunar-polar-scout", "earth-observation"])
def test_every_starter_schedule_is_monotonic(scenario: str) -> None:
    s = build_schedule(make_state(scenario))
    days = [d for _, d in s.transitions]
    assert days == sorted(days) and days[0] == 0.0


def test_empty_plans_still_schedule_all_phases() -> None:
    state = _with_ops(make_state(), observation_plan=[], downlink_plan=[])
    s = build_schedule(state)
    assert [p for p, _ in s.transitions] == [*SIM_PHASES, "complete"]
    days = [d for _, d in s.transitions]
    assert days == sorted(days) and days[-1] == 420.0

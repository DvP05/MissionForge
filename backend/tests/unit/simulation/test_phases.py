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


STARTERS = ("neo-rendezvous", "lunar-polar-scout", "earth-observation")


@pytest.mark.parametrize("scenario", STARTERS)
def test_every_starter_phase_has_positive_length(scenario: str) -> None:
    s = build_schedule(make_state(scenario))
    days = [d for _, d in s.transitions]
    lengths = {p: b - a for (p, a), b in zip(s.transitions, days[1:], strict=False)}
    assert set(lengths) == set(SIM_PHASES)
    assert all(v > 0.0 for v in lengths.values()), lengths


@pytest.mark.parametrize("scenario", STARTERS)
def test_arrival_is_time_of_flight_when_transfer_fits(scenario: str) -> None:
    state = make_state(scenario)
    s = build_schedule(state)
    tof = state.trajectory.time_of_flight_days
    assert tof is not None
    if tof > s.start_of("cruise"):
        assert s.transfer and s.arrival_day == tof
        assert s.start_of("cruise") < s.start_of("mid-course") < s.start_of("approach") < tof


def test_lunar_schedule_days() -> None:
    s = build_schedule(make_state("lunar-polar-scout"))  # TOF 5 d, first observation day 20
    days = dict(s.transitions)
    assert s.transfer and s.arrival_day == 5.0
    assert days["commissioning"] == pytest.approx(0.25)  # 5 % of TOF
    assert days["cruise"] == pytest.approx(1.5)  # + 25 % of TOF
    assert days["approach"] == pytest.approx(3.25)  # at most half the transfer
    assert days["mid-course"] == pytest.approx(2.375)
    assert days["science-ops"] == 20.0


def test_leo_schedule_has_orbit_phases() -> None:
    s = build_schedule(make_state("earth-observation"))  # TOF 0, first observation day 30
    days = dict(s.transitions)
    assert not s.transfer
    assert days["cruise"] == pytest.approx(8.5)  # 1 d launch + 7.5 d commissioning (25 % of S)
    assert days["mid-course"] == pytest.approx(9.5)  # 1 d orbit raising (gameplay)
    assert days["approach"] == pytest.approx(10.5)  # 1 d orbit trim (gameplay)
    assert s.arrival_day == days["approach"]
    assert days["science-ops"] == 30.0


def test_mission_end_extends_to_last_contact() -> None:
    state = _with_ops(make_state(), mission_duration_days=400.0)  # last contact ends 408.33
    s = build_schedule(state)
    assert s.end_day == pytest.approx(408.0 + 8.0 / 24.0)
    assert s.planned_end_day == 400.0

"""Mission phase schedule (architecture 9.1, M14).

Phases run in a fixed order; each starts on a mission day derived from the design:

* ``launch-deployment`` starts on day 0.
* ``commissioning`` starts after ``LAUNCH_DEPLOYMENT_DAYS`` and ``cruise`` after a further
  ``COMMISSIONING_DAYS`` (gameplay defaults). Both are capped at 5 % / 25 % of the
  pre-science window so short missions (LEO, lunar) still fit.
* Pre-science window ``S`` = first observation start day; without observations it is the
  time of flight, else half the mission duration.
* Arrival ``A`` = time of flight (``timeOfFlightDays``, else arrival - departure date),
  clamped to [cruise start, S]; without a time of flight ``A = S``.
* ``approach`` starts ``APPROACH_DAYS`` before arrival (not before cruise start) and lasts
  until ``S``; ``mid-course`` starts at the midpoint of cruise start .. approach start.
* ``science-ops`` starts at ``S`` and lasts until the last observation ends.
* ``downlink-return`` lasts until the mission end = max(mission duration, last observation
  end, last contact end); ``complete`` is entered at the mission end.

Boundaries are non-decreasing; a phase can have zero length on a degenerate plan. A day on
a boundary belongs to the phase being entered.
"""

from dataclasses import dataclass

from app.schemas.mission import MissionState
from app.schemas.simulation import Phase

SIM_PHASES: tuple[Phase, ...] = (
    "launch-deployment",
    "commissioning",
    "cruise",
    "mid-course",
    "approach",
    "science-ops",
    "downlink-return",
)

# gameplay-estimate phase lengths (days), not mission-specific engineering values
LAUNCH_DEPLOYMENT_DAYS = 1.0
COMMISSIONING_DAYS = 14.0
APPROACH_DAYS = 30.0
LAUNCH_MAX_FRACTION = 0.05  # of the pre-science window
COMMISSIONING_MAX_FRACTION = 0.25
MID_COURSE_FRACTION = 0.5  # of cruise start .. approach start

PHASE_ASSUMPTIONS: tuple[str, ...] = (
    f"Launch/deployment lasts {LAUNCH_DEPLOYMENT_DAYS:g} d and commissioning "
    f"{COMMISSIONING_DAYS:g} d (gameplay defaults, capped to 5 % / 25 % of the time before "
    "science starts).",
    f"Approach starts {APPROACH_DAYS:g} d before arrival; mid-course starts halfway through "
    "the cruise (gameplay defaults).",
    "Science operations span the observation plan; downlink-return runs to the end of the mission.",
)


@dataclass(frozen=True)
class PhaseSchedule:
    transitions: tuple[tuple[Phase, float], ...]  # (phase entered, mission day), incl. end
    arrival_day: float
    end_day: float

    def phase_at(self, day: float) -> Phase:
        current: Phase = self.transitions[0][0]
        for phase, start in self.transitions:
            if day >= start:
                current = phase
            else:
                break
        return current

    def start_of(self, phase: Phase) -> float:
        return next(d for p, d in self.transitions if p == phase)


def time_of_flight_days(state: MissionState) -> float | None:
    traj = state.trajectory
    if traj.time_of_flight_days is not None:
        return max(0.0, traj.time_of_flight_days)
    if traj.arrival_date is not None:
        return float(max(0, (traj.arrival_date - traj.departure_date).days))
    return None


def _clamp(x: float, lo: float, hi: float) -> float:
    return min(max(x, lo), hi)


def build_schedule(state: MissionState) -> PhaseSchedule:
    ops = state.operations
    duration = ops.mission_duration_days
    tof = time_of_flight_days(state)
    obs = ops.observation_plan
    obs_end = max((o.start_day + o.duration_hours / 24.0 for o in obs), default=None)
    contact_end = max(
        (d.start_day + d.duration_minutes / 1440.0 for d in ops.downlink_plan), default=0.0
    )
    end = max(duration, obs_end or 0.0, contact_end)

    if obs:
        sci = min(o.start_day for o in obs)
    else:
        sci = tof if tof is not None else 0.5 * duration
    sci = _clamp(sci, 0.0, end)

    launch = min(LAUNCH_DEPLOYMENT_DAYS, LAUNCH_MAX_FRACTION * sci)
    commissioning = min(COMMISSIONING_DAYS, COMMISSIONING_MAX_FRACTION * sci)
    cruise = launch + commissioning
    arrival = _clamp(tof if tof is not None else sci, cruise, sci)
    approach = max(cruise, arrival - APPROACH_DAYS)
    mid_course = cruise + MID_COURSE_FRACTION * (approach - cruise)
    downlink = _clamp(obs_end if obs_end is not None else sci, sci, end)

    days = (0.0, launch, cruise, mid_course, approach, sci, downlink)
    transitions: tuple[tuple[Phase, float], ...] = (
        *zip(SIM_PHASES, days, strict=True),
        ("complete", end),
    )
    return PhaseSchedule(transitions=transitions, arrival_day=arrival, end_day=end)


__all__ = [
    "APPROACH_DAYS",
    "COMMISSIONING_DAYS",
    "LAUNCH_DEPLOYMENT_DAYS",
    "PHASE_ASSUMPTIONS",
    "SIM_PHASES",
    "PhaseSchedule",
    "build_schedule",
    "time_of_flight_days",
]

"""Mission phase schedule (architecture 9.1, M14).

Phases run in a fixed order; each starts on a mission day derived from the design. ``T`` is
the time of flight (``timeOfFlightDays``, else arrival - departure date) and ``S`` the
science start (first observation start).

Transfer missions (``T > 0``, e.g. NEO, lunar):

* ``launch-deployment`` starts on day 0, ``commissioning`` after
  min(``LAUNCH_DEPLOYMENT_DAYS``, 5 % of T) and ``cruise`` after a further
  min(``COMMISSIONING_DAYS``, 25 % of T) (gameplay defaults). Bounding both by T means
  cruise always starts before arrival, so arrival is never moved off the time of flight.
* Arrival ``A = T``. Only when observations start before T (a plan observing in transit)
  is it clamped to ``S`` (not below cruise start).
* ``approach`` starts at max(A - ``APPROACH_DAYS``, midpoint of cruise start .. A): the
  approach never takes more than half the transfer, so cruise and mid-course are positive.
* ``mid-course`` starts halfway between cruise start and approach start.
* ``approach`` lasts until S (or A when there are no observations).

No-transfer missions (``T`` = 0 or unknown, e.g. LEO): launch and commissioning are capped at
5 % / 25 % of S (S = half the mission duration without observations); ``cruise`` (orbit
raising / checkout) and ``mid-course`` (orbit trim) each last min(``ORBIT_PHASE_DAYS``,
5 % of S) (gameplay durations, so every phase is entered); arrival (on station) is the
start of ``approach`` (orbit acquisition), which lasts until S.

Both: ``science-ops`` runs from S to the end of the last observation; ``downlink-return``
until the mission end = max(mission duration, last observation end, last contact end),
extended by ``MIN_DOWNLINK_RETURN_DAYS`` when it would otherwise have no length;
``complete`` is entered at the mission end.

Boundaries are non-decreasing. Every phase has positive length on the starter scenarios; a
degenerate plan (e.g. no observations at all on day 0) may produce zero-length phases. A
day on a boundary belongs to the phase being entered.
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
ORBIT_PHASE_DAYS = 1.0  # cruise / mid-course length when there is no transfer
MIN_DOWNLINK_RETURN_DAYS = 1.0
LAUNCH_MAX_FRACTION = 0.05  # of the time of flight (transfer) or the time before science
COMMISSIONING_MAX_FRACTION = 0.25
ORBIT_PHASE_MAX_FRACTION = 0.05
MID_COURSE_FRACTION = 0.5  # of cruise start .. approach start
APPROACH_MAX_FRACTION = 0.5  # of cruise start .. arrival

PHASE_ASSUMPTIONS: tuple[str, ...] = (
    f"Launch/deployment lasts {LAUNCH_DEPLOYMENT_DAYS:g} d and commissioning "
    f"{COMMISSIONING_DAYS:g} d (gameplay defaults, capped to 5 % / 25 % of the time of "
    "flight, or of the time before science when there is no transfer).",
    f"Approach starts {APPROACH_DAYS:g} d before arrival (at most half the transfer); "
    "mid-course starts halfway through the cruise (gameplay defaults).",
    f"Without an interplanetary transfer, cruise (orbit raising / checkout) and mid-course "
    f"(orbit trim) each last {ORBIT_PHASE_DAYS:g} d (gameplay durations).",
    "Science operations span the observation plan; downlink-return runs to the end of the mission.",
)


@dataclass(frozen=True)
class PhaseSchedule:
    transitions: tuple[tuple[Phase, float], ...]  # (phase entered, mission day), incl. end
    arrival_day: float
    end_day: float
    transfer: bool  # True when the trajectory has a positive time of flight
    planned_end_day: float  # mission duration from the operations plan

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


def build_schedule(state: MissionState) -> PhaseSchedule:
    ops = state.operations
    duration = ops.mission_duration_days
    tof = time_of_flight_days(state)
    obs = ops.observation_plan
    first_obs = min((o.start_day for o in obs), default=None)
    obs_end = max((o.start_day + o.duration_hours / 24.0 for o in obs), default=None)
    contact_end = max(
        (d.start_day + d.duration_minutes / 1440.0 for d in ops.downlink_plan), default=0.0
    )
    transfer = tof is not None and tof > 0.0

    if tof is not None and tof > 0.0:
        launch = min(LAUNCH_DEPLOYMENT_DAYS, LAUNCH_MAX_FRACTION * tof)
        commissioning = min(COMMISSIONING_DAYS, COMMISSIONING_MAX_FRACTION * tof)
        cruise = launch + commissioning
        sci_raw = first_obs if first_obs is not None else tof
        arrival = tof if sci_raw >= tof else max(sci_raw, cruise)
        sci = max(sci_raw, arrival)
        approach = max(arrival - APPROACH_DAYS, cruise + APPROACH_MAX_FRACTION * (arrival - cruise))
        mid_course = cruise + MID_COURSE_FRACTION * (approach - cruise)
    else:
        sci = first_obs if first_obs is not None else 0.5 * duration
        launch = min(LAUNCH_DEPLOYMENT_DAYS, LAUNCH_MAX_FRACTION * sci)
        commissioning = min(COMMISSIONING_DAYS, COMMISSIONING_MAX_FRACTION * sci)
        cruise = launch + commissioning
        orbit = min(ORBIT_PHASE_DAYS, ORBIT_PHASE_MAX_FRACTION * sci)
        mid_course = cruise + orbit
        approach = mid_course + orbit
        arrival = approach

    downlink = max(obs_end if obs_end is not None else sci, sci)
    end = max(duration, contact_end, downlink)
    if end <= downlink:
        end = downlink + MIN_DOWNLINK_RETURN_DAYS

    days = (0.0, launch, cruise, mid_course, approach, sci, downlink)
    transitions: tuple[tuple[Phase, float], ...] = (
        *zip(SIM_PHASES, days, strict=True),
        ("complete", end),
    )
    return PhaseSchedule(
        transitions=transitions,
        arrival_day=arrival,
        end_day=end,
        transfer=transfer,
        planned_end_day=duration,
    )


__all__ = [
    "APPROACH_DAYS",
    "COMMISSIONING_DAYS",
    "LAUNCH_DEPLOYMENT_DAYS",
    "MIN_DOWNLINK_RETURN_DAYS",
    "ORBIT_PHASE_DAYS",
    "PHASE_ASSUMPTIONS",
    "SIM_PHASES",
    "PhaseSchedule",
    "build_schedule",
    "time_of_flight_days",
]

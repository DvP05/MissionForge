"""Cross-reference validation for MissionState (M06).

Issue codes: DUPLICATE_ID (objective/measurement/instrument ids), UNKNOWN_MEASUREMENT
(observation plan references a missing measurement), UNKNOWN_COMPONENT (architecture id
not in the catalogue), DATE_ORDER (arrival before departure), FRACTION_RANGE (duty
cycle / probability outside [0,1]; defensive, the models already enforce it).
"""

import re
from collections import Counter
from typing import Protocol

from app.schemas.mission import MAX_TITLE_LENGTH, MissionState, ValidationIssue

_TAGS = re.compile(r"<[^>]*>")
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_SPACE = re.compile(r"\s+")


class CatalogLookup(Protocol):
    def has(self, component_id: str) -> bool: ...


def sanitize_title(s: str) -> str:
    """Strip HTML tags and control chars, collapse whitespace, trim, cap at 80 chars."""
    s = _TAGS.sub("", s)
    s = _CONTROL.sub(" ", s)
    s = _SPACE.sub(" ", s).strip()
    return s[:MAX_TITLE_LENGTH].rstrip()


_SINGLE_ID_FIELDS = (
    ("launch_vehicle_id", "launchVehicleId"),
    ("bus_id", "busId"),
    ("propulsion_id", "propulsionId"),
    ("power_id", "powerId"),
    ("adcs_id", "adcsId"),
    ("communications_id", "communicationsId"),
    ("thermal_id", "thermalId"),
    ("cdh_id", "cdhId"),
    ("ground_segment_id", "groundSegmentId"),
)


def _duplicates(ids: list[str]) -> list[str]:
    return [i for i, n in Counter(ids).items() if n > 1]


def validate_mission_state(state: MissionState, catalog: CatalogLookup) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    def add(code: str, path: str, message: str) -> None:
        issues.append(ValidationIssue(code=code, path=path, message=message))

    objectives = state.science_objectives
    for dup in _duplicates([o.id for o in objectives]):
        add("DUPLICATE_ID", "scienceObjectives", f"duplicate objective id {dup!r}")

    measurement_ids = [m.id for o in objectives for m in o.required_measurements]
    for dup in _duplicates(measurement_ids):
        add(
            "DUPLICATE_ID",
            "scienceObjectives.requiredMeasurements",
            f"duplicate measurement id {dup!r}",
        )

    arch = state.architecture
    for dup in _duplicates(arch.instrument_ids):
        add("DUPLICATE_ID", "architecture.instrumentIds", f"duplicate instrument id {dup!r}")

    known = set(measurement_ids)
    for i, item in enumerate(state.operations.observation_plan):
        if item.measurement_id not in known:
            add(
                "UNKNOWN_MEASUREMENT",
                f"operations.observationPlan[{i}].measurementId",
                f"unknown measurement {item.measurement_id!r}",
            )
        if not 0.0 <= item.duty_cycle <= 1.0:
            add("FRACTION_RANGE", f"operations.observationPlan[{i}].dutyCycle", "must be in [0, 1]")

    p = state.constraints.minimum_success_probability
    if p is not None and not 0.0 <= p <= 1.0:
        add("FRACTION_RANGE", "constraints.minimumSuccessProbability", "must be in [0, 1]")

    for attr, alias in _SINGLE_ID_FIELDS:
        cid: str = getattr(arch, attr)
        if not catalog.has(cid):
            add("UNKNOWN_COMPONENT", f"architecture.{alias}", f"unknown component {cid!r}")
    for i, cid in enumerate(arch.instrument_ids):
        if not catalog.has(cid):
            add(
                "UNKNOWN_COMPONENT",
                f"architecture.instrumentIds[{i}]",
                f"unknown component {cid!r}",
            )

    traj = state.trajectory
    if traj.arrival_date is not None and traj.arrival_date < traj.departure_date:
        add("DATE_ORDER", "trajectory.arrivalDate", "arrival date precedes departure date")

    return issues

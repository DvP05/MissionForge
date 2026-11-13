from typing import Any

from app.domain.mission.validation import sanitize_title, validate_mission_state
from app.schemas.mission import MissionState
from tests.unit.mission.test_mission_state import raw


class FakeCatalog:
    def __init__(self, ids: set[str]) -> None:
        self.ids = ids

    def has(self, component_id: str) -> bool:
        return component_id in self.ids


ALL = FakeCatalog({"lv", "bus", "prop", "pow", "adcs", "comm", "th", "cdh", "cam", "gs"})


def codes(d: dict[str, Any], cat: FakeCatalog = ALL) -> list[str]:
    return [i.code for i in validate_mission_state(MissionState.model_validate(d), cat)]


def test_valid_state_no_issues() -> None:
    assert codes(raw()) == []


def test_duplicate_objective_ids() -> None:
    d = raw()
    obj = d["scienceObjectives"][0]
    d["scienceObjectives"].append({**obj, "requiredMeasurements": []})
    assert codes(d) == ["DUPLICATE_ID"]


def test_duplicate_measurement_ids_across_objectives() -> None:
    d = raw()
    obj = d["scienceObjectives"][0]
    d["scienceObjectives"].append({**obj, "id": "obj2"})
    assert codes(d) == ["DUPLICATE_ID"]


def test_duplicate_instrument_ids() -> None:
    d = raw()
    d["architecture"]["instrumentIds"] = ["cam", "cam"]
    assert codes(d) == ["DUPLICATE_ID"]


def test_unknown_measurement() -> None:
    d = raw()
    d["operations"]["observationPlan"][0]["measurementId"] = "nope"
    issues = validate_mission_state(MissionState.model_validate(d), ALL)
    assert [(i.code, i.path) for i in issues] == [
        ("UNKNOWN_MEASUREMENT", "operations.observationPlan[0].measurementId")
    ]


def test_unknown_component_each_field_and_instrument() -> None:
    cat = FakeCatalog(ALL.ids - {"bus", "cam"})
    issues = validate_mission_state(MissionState.model_validate(raw()), cat)
    assert {(i.code, i.path) for i in issues} == {
        ("UNKNOWN_COMPONENT", "architecture.busId"),
        ("UNKNOWN_COMPONENT", "architecture.instrumentIds[0]"),
    }


def test_date_order() -> None:
    d = raw()
    d["trajectory"]["arrivalDate"] = "2029-01-01"
    assert codes(d) == ["DATE_ORDER"]


def test_arrival_equal_departure_ok_and_none_ok() -> None:
    d = raw()
    d["trajectory"]["arrivalDate"] = "2030-01-01"
    assert codes(d) == []
    del d["trajectory"]["arrivalDate"]
    assert codes(d) == []


def test_sanitize_title() -> None:
    assert sanitize_title("<b>Hi</b>\t\x07 there  ") == "Hi there"
    assert len(sanitize_title("x" * 200)) == 80
    assert sanitize_title("") == ""

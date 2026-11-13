import copy
import json
import math
import re
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.mission import MissionState

PROV = {"fidelity": "gameplay-estimate", "sourceName": "test"}


def raw() -> dict[str, Any]:
    return {
        "schemaVersion": "1.0",
        "missionId": "m1",
        "title": "Test mission",
        "scenarioId": "neo-rendezvous",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
        "designRevision": 0,
        "scienceObjectives": [
            {
                "id": "obj1",
                "title": "T",
                "question": "Q?",
                "priority": 1.0,
                "requiredMeasurements": [
                    {
                        "id": "meas1",
                        "description": "d",
                        "instrumentCapability": "imaging",
                        "targetThreshold": {"value": 1.0, "unit": "m", "provenance": PROV},
                        "coverageWeight": 1.0,
                    }
                ],
            }
        ],
        "destination": {"bodyId": "b", "name": "Bennu", "bodyType": "asteroid"},
        "trajectory": {
            "provider": "scenario-preset",
            "optionId": "o1",
            "departureDate": "2030-01-01",
            "arrivalDate": "2030-06-01",
        },
        "architecture": {
            "launchVehicleId": "lv",
            "busId": "bus",
            "propulsionId": "prop",
            "powerId": "pow",
            "adcsId": "adcs",
            "communicationsId": "comm",
            "thermalId": "th",
            "cdhId": "cdh",
            "instrumentIds": ["cam"],
            "groundSegmentId": "gs",
        },
        "operations": {
            "missionDurationDays": 100.0,
            "observationPlan": [
                {"measurementId": "meas1", "startDay": 1.0, "durationHours": 2.0, "dutyCycle": 0.5}
            ],
            "downlinkPlan": [
                {"startDay": 1.0, "durationMinutes": 30.0, "dataRateBitsPerSecond": 1000.0}
            ],
            "safeModePolicy": "balanced",
            "autonomyLevel": "supervised",
        },
        "constraints": {
            "maximumBudgetUsd": 1e8,
            "massMarginFraction": 0.2,
            "powerMarginFraction": 0.2,
            "dataMarginFraction": 0.2,
            "deltaVMarginKmPerS": 0.1,
        },
        "randomSeed": 42,
    }


def snake(d: Any) -> Any:
    if isinstance(d, dict):
        return {
            re.sub(r"([A-Z])", lambda m: "_" + m.group(1).lower(), k): snake(v)
            for k, v in d.items()
        }
    if isinstance(d, list):
        return [snake(x) for x in d]
    return d


def test_parses_camel_case() -> None:
    s = MissionState.model_validate(raw())
    assert s.mission_id == "m1"
    assert s.operations.observation_plan[0].duty_cycle == 0.5


def test_parses_snake_case() -> None:
    s = MissionState.model_validate(snake(raw()))
    assert s.architecture.instrument_ids == ["cam"]


def test_unknown_field_rejected() -> None:
    d = raw()
    d["bogus"] = 1
    with pytest.raises(ValidationError):
        MissionState.model_validate(d)


def test_duty_cycle_above_one_rejected() -> None:
    d = raw()
    d["operations"]["observationPlan"][0]["dutyCycle"] = 1.2
    with pytest.raises(ValidationError):
        MissionState.model_validate(d)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, True, "1.0"])
def test_non_finite_or_non_float_rejected(bad: object) -> None:
    d = raw()
    d["operations"]["missionDurationDays"] = bad
    with pytest.raises(ValidationError):
        MissionState.model_validate(d)


def test_nan_rejected_in_json() -> None:
    text = json.dumps(raw()).replace('"startDay": 1.0', '"startDay": NaN', 1)
    with pytest.raises(ValidationError):
        MissionState.model_validate_json(text)


def test_title_sanitised_on_parse() -> None:
    d = raw()
    d["title"] = "<script>x</script>  Hi\x00\n there"
    assert MissionState.model_validate(d).title == "x Hi there"


def test_bad_scenario_rejected() -> None:
    d = raw()
    d["scenarioId"] = "mars"
    with pytest.raises(ValidationError):
        MissionState.model_validate(d)


def test_no_derived_total_fields() -> None:
    names = set(MissionState.model_fields)
    assert not [n for n in names if "total" in n]
    assert "score" not in names
    assert "feasible" not in names


def test_round_trip_by_alias() -> None:
    s = MissionState.model_validate(raw())
    again = MissionState.model_validate(copy.deepcopy(s.model_dump(by_alias=True, mode="json")))
    assert again == s

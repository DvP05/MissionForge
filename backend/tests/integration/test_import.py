"""POST /api/mission/import and /api/mission/replay (Task 4.5, M18, Review Focus #4, #5)."""

import copy
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_clock
from app.main import create_app

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
IMPORT = "/api/mission/import"
REPLAY = "/api/mission/replay"
SOLAR = "scenario-solar-event"


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_clock] = lambda: lambda: NOW
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _state(client: TestClient) -> dict[str, Any]:
    state: dict[str, Any] = client.get("/api/templates/neo-rendezvous/default-mission").json()[
        "data"
    ]
    state["architecture"]["communicationsId"] = "comms-xband-medium"
    return state


def _run(client: TestClient, state: dict[str, Any], seed: int = 42) -> dict[str, Any]:
    r = client.post("/api/mission/simulate", json={"missionState": state, "randomSeed": seed})
    run: dict[str, Any] = r.json()["data"]["run"]
    return run


def _package(state: dict[str, Any], runs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "packageSchemaVersion": "1.0",
        "exportedAt": "2026-11-14T10:00:00Z",
        "mission": state,
        "latestAnalysis": None,
        "runs": runs or [],
        "evidence": [],
        "manifest": {
            "appVersion": "0.1.0",
            "engineVersion": "0.1.0",
            "catalogVersion": "0.1.0",
            "scenarioVersion": "x",
        },
    }


def _post(client: TestClient, payload: Any) -> Any:
    return client.post(
        IMPORT, content=json.dumps(payload), headers={"Content-Type": "application/json"}
    )


def test_valid_round_trip_keeps_mission_and_runs(client: TestClient) -> None:
    state = _state(client)
    run = _run(client, state)
    r = _post(client, _package(state, [run]))
    body = r.json()
    assert r.status_code == 200 and body["ok"] is True
    data = body["data"]
    assert data["package"]["mission"] == state  # exact round trip of the MissionState
    assert data["package"]["runs"] == [run]
    assert data["package"]["latestAnalysis"]["designRevision"] == state["designRevision"]
    [status] = data["replay"]
    assert status["runId"] == run["runId"]
    assert status["status"] == "identical-replay" and status["mismatches"] == []
    assert status["analysis"]["engineVersion"] == "0.1.0"


def test_package_larger_than_default_limit_is_accepted(client: TestClient) -> None:
    state = _state(client)
    runs = [_run(client, state, seed=s) for s in (1, 2, 3, 4)]
    payload = json.dumps(_package(state, runs))
    assert len(payload) > 256 * 1024  # over the normal request limit, under the import limit
    r = client.post(IMPORT, content=payload, headers={"Content-Type": "application/json"})
    assert r.status_code == 200 and len(r.json()["data"]["replay"]) == 4


def test_oversized_body_is_rejected_with_413(client: TestClient) -> None:
    big = b'{"x":"' + b"a" * (5 * 1024 * 1024) + b'"}'
    r = client.post(IMPORT, content=big, headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.parametrize("body", [b"{not json", b"", b"[1,2]", b'"text"'])
def test_invalid_json_or_shape_is_rejected(client: TestClient, body: bytes) -> None:
    r = client.post(IMPORT, content=body, headers={"Content-Type": "application/json"})
    assert r.status_code == 422 and r.json()["ok"] is False
    assert r.json()["error"]["code"] in {"INVALID_JSON", "INVALID_PACKAGE"}


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_non_standard_json_constants_are_rejected(client: TestClient, literal: str) -> None:
    state = _state(client)
    text = json.dumps(_package(state)).replace('"randomSeed": 42', f'"randomSeed": {literal}')
    text = text.replace('"designRevision": 0', f'"designRevision": {literal}', 1)
    assert literal in text
    r = client.post(IMPORT, content=text, headers={"Content-Type": "application/json"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_JSON"


def test_wrong_mission_schema_version_is_rejected_not_reinterpreted(client: TestClient) -> None:
    state = _state(client)
    state["schemaVersion"] = "9.9"
    r = _post(client, _package(state))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "UNSUPPORTED_SCHEMA_VERSION"


def test_wrong_package_version_is_rejected(client: TestClient) -> None:
    pkg = _package(_state(client))
    pkg["packageSchemaVersion"] = "9.9"
    r = _post(client, pkg)
    assert r.status_code == 422 and r.json()["error"]["code"] == "UNSUPPORTED_PACKAGE_VERSION"
    r = _post(client, {"schemaVersion": "9.9"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "UNSUPPORTED_PACKAGE_VERSION"


def test_html_in_titles_is_sanitised(client: TestClient) -> None:
    state = _state(client)
    run = _run(client, state)
    state["title"] = 'Hello <img src=x onerror="alert(1)"> world <script>x</script>'
    run["inputSnapshot"]["title"] = "<b>Snap</b>"
    r = _post(client, _package(state, [run]))
    assert r.status_code == 200
    pkg = r.json()["data"]["package"]
    assert "<" not in pkg["mission"]["title"] and "onerror" not in pkg["mission"]["title"]
    assert pkg["mission"]["title"].startswith("Hello")
    assert pkg["runs"][0]["inputSnapshot"]["title"] == "Snap"


def test_unknown_component_is_a_structured_error(client: TestClient) -> None:
    state = _state(client)
    state["architecture"]["busId"] = "bus-does-not-exist"
    r = _post(client, _package(state))
    assert r.status_code == 422 and r.json()["error"]["code"] == "CATALOG_ITEM_NOT_FOUND"


def test_unknown_fields_and_bad_types_are_listed_without_echoing_input(
    client: TestClient,
) -> None:
    state = _state(client)
    pkg = _package(state)
    pkg["unexpected"] = "SECRET-VALUE"
    r = _post(client, pkg)
    err = r.json()["error"]
    assert r.status_code == 422 and err["code"] == "INVALID_PACKAGE"
    assert err["details"]["fields"] and "SECRET-VALUE" not in r.text


def test_run_with_mismatched_snapshot_is_rejected(client: TestClient) -> None:
    state = _state(client)
    run = _run(client, state)
    bad = copy.deepcopy(run)
    bad["inputSnapshot"]["designRevision"] = 7  # snapshot no longer matches the run
    r = _post(client, _package(state, [bad]))
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_PACKAGE"
    bad = copy.deepcopy(run)
    bad["manifest"]["seed"] = 999  # manifest disagrees with the run
    assert _post(client, _package(state, [bad])).status_code == 422


def test_run_of_another_mission_is_rejected(client: TestClient) -> None:
    state = _state(client)
    run = _run(client, state)
    other = copy.deepcopy(state)
    other["missionId"] = "mission-other0000001"
    r = _post(client, _package(other, [run]))
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_PACKAGE"


def test_duplicate_run_ids_and_too_many_runs_are_rejected(client: TestClient) -> None:
    state = _state(client)
    run = _run(client, state)
    assert _post(client, _package(state, [run, run])).status_code == 422
    r = _post(client, _package(state, [run] * 21))
    assert r.status_code == 422 and r.json()["error"]["code"] == "PACKAGE_TOO_MANY_RUNS"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("engineVersion", "9.9.9"),
        ("catalogVersion", "9.9.9"),
        ("scenarioVersion", "9.9.9"),
    ],
)
def test_version_mismatch_is_reported_never_identical(
    client: TestClient, field: str, value: str
) -> None:
    state = _state(client)
    run = _run(client, state)
    run["manifest"][field] = value
    if field in ("engineVersion", "catalogVersion"):
        run[field] = value  # validator requires run and manifest to agree
    r = _post(client, _package(state, [run]))
    assert r.status_code == 200
    [status] = r.json()["data"]["replay"]
    assert status["status"] == "version-mismatch"
    assert [m["field"] for m in status["mismatches"]] == [field]
    assert status["mismatches"][0]["recorded"] == "9.9.9"


def test_missing_event_set_is_a_mismatch(client: TestClient) -> None:
    state = _state(client)
    run = _run(client, state)
    run["scenarioEventSetId"] = "no-such-event-set"
    run["manifest"]["eventSetId"] = "no-such-event-set"
    r = _post(client, _package(state, [run]))
    [status] = r.json()["data"]["replay"]
    assert status["status"] == "version-mismatch"
    assert status["mismatches"][0]["field"] == "eventSet"


def test_nothing_is_stored_server_side(client: TestClient) -> None:
    state = _state(client)
    run = _run(client, state)
    _post(client, _package(state, [run]))
    # Only runs created by /simulate live in the run store; import must not add or alter any.
    bogus = copy.deepcopy(run)
    bogus["runId"] = "run-imported-only"
    _post(client, _package(state, [bogus]))
    assert client.get("/api/mission/run/run-imported-only").status_code == 404


# ---- replay -------------------------------------------------------------------------------


def test_replay_of_unmodified_run_is_identical(client: TestClient) -> None:
    run = _run(client, _state(client))
    r = client.post(REPLAY, json={"run": run})
    data = r.json()["data"]
    assert r.status_code == 200 and data["identical"] is True
    assert data["status"] == "identical-replay" and data["mismatches"] == []
    assert json.dumps(data["run"], sort_keys=True) == json.dumps(run, sort_keys=True)


def test_replay_reproduces_player_decisions(client: TestClient) -> None:
    run = _run(client, _state(client))
    branched = client.post(
        f"/api/mission/run/{run['runId']}/decision",
        json={"eventId": SOLAR, "choiceId": "pause-science"},
    ).json()["data"]["run"]
    assert any(d["decisionMaker"] == "player" for d in branched["decisions"])
    r = client.post(REPLAY, json={"run": branched})
    data = r.json()["data"]
    assert data["identical"] is True
    assert [e["id"] for e in data["run"]["events"]] == [e["id"] for e in branched["events"]]
    assert data["run"]["telemetry"] == branched["telemetry"]
    assert data["run"]["decisions"] == branched["decisions"]


def test_replay_with_different_versions_does_not_claim_identity(client: TestClient) -> None:
    run = _run(client, _state(client))
    run["engineVersion"] = run["manifest"]["engineVersion"] = "0.0.1"
    r = client.post(REPLAY, json={"run": run})
    data = r.json()["data"]
    assert r.status_code == 200 and r.json()["ok"] is True
    assert data["identical"] is False and data["status"] == "version-mismatch"
    assert data["run"] is None
    assert data["mismatches"][0] == {
        "field": "engineVersion",
        "recorded": "0.0.1",
        "current": "0.1.0",
    }


def test_replay_of_tampered_output_is_diverged_not_identical(client: TestClient) -> None:
    run = _run(client, _state(client))
    run["telemetry"][0]["value"] = run["telemetry"][0]["value"] + 1.0
    data = client.post(REPLAY, json={"run": run}).json()["data"]
    assert data["identical"] is False and data["status"] == "diverged"


def test_replay_ignores_app_version_stamp(client: TestClient) -> None:
    run = _run(client, _state(client))
    run["manifest"]["appVersion"] = "0.0.1-old"
    data = client.post(REPLAY, json={"run": run}).json()["data"]
    assert data["identical"] is True


def test_replay_rejects_inconsistent_run(client: TestClient) -> None:
    run = _run(client, _state(client))
    run["inputSnapshot"]["designRevision"] = 3
    r = client.post(REPLAY, json={"run": run})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_replay_survives_a_javascript_json_round_trip(client: TestClient) -> None:
    """Browser storage / export files turn 275.0 into 275; that is the same recorded value."""
    run = _run(client, _state(client))

    def js_like(o: Any) -> Any:
        if isinstance(o, float) and o.is_integer():
            return int(o)
        if isinstance(o, dict):
            return {k: js_like(v) for k, v in o.items()}
        if isinstance(o, list):
            return [js_like(v) for v in o]
        return o

    stripped = js_like(run)
    assert json.dumps(stripped) != json.dumps(run)  # the transport really changed the text
    data = client.post(REPLAY, json={"run": stripped}).json()["data"]
    assert data["identical"] is True and data["status"] == "identical-replay"

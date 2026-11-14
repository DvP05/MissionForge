"""POST /api/mission/health (Task 6.7): monitor a recorded run against its nominal model."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

HEALTH = "/api/mission/health"


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        yield c


def _run(client: TestClient, scenario: str, comms: str | None = None) -> dict[str, Any]:
    state: dict[str, Any] = client.get(f"/api/templates/{scenario}/default-mission").json()["data"]
    if comms:
        state["architecture"]["communicationsId"] = comms
    body = client.post(
        "/api/mission/simulate",
        json={"missionState": state, "randomSeed": 42, "experimental": True},
    ).json()
    run: dict[str, Any] = body["data"]["run"]
    return run


def test_report_shows_raw_envelope_residual_ewma_and_rule(client: TestClient) -> None:
    run = _run(client, "neo-rendezvous", "comms-xband-medium")
    body = client.post(HEALTH, json={"run": run}).json()
    assert body["ok"] is True, body
    data = body["data"]
    assert data["runId"] == run["runId"] and data["nominalEventSetId"] == "nominal-v1"
    categories = {c["category"] for c in data["channels"]}
    assert {"power-thermal", "attitude-pointing", "comms-data"} <= categories
    point = data["channels"][0]["points"][0]
    assert set(point) >= {"observed", "expected", "residual", "ewma", "persistence", "state"}
    assert all(c["config"]["rationale"] for c in data["channels"])
    assert data["assumptions"]


def test_findings_map_to_scenario_events_and_recovery_decisions(client: TestClient) -> None:
    run = _run(client, "neo-rendezvous", "comms-xband-medium")
    data = client.post(HEALTH, json={"run": run}).json()["data"]
    assert data["findings"], "the solar event should leave a mark on the telemetry"
    event_ids = {e["id"] for e in run["events"]}
    for f in data["findings"]:
        if f["likelyFalsePositive"]:
            assert f["relatedEventId"] is None and "false positive" in f["explanation"]
        else:
            assert f["relatedEventId"] in event_ids
    explained = [f for f in data["findings"] if f["relatedEventId"]]
    assert any(f["recoveryDecision"] for f in explained)


def test_nominal_run_has_no_findings_and_is_deterministic(client: TestClient) -> None:
    state: dict[str, Any] = client.get("/api/templates/neo-rendezvous/default-mission").json()[
        "data"
    ]
    state["architecture"]["communicationsId"] = "comms-xband-medium"
    run = client.post(
        "/api/mission/simulate",
        json={"missionState": state, "randomSeed": 42, "scenarioEventSetId": "nominal-v1"},
    ).json()["data"]["run"]
    a = client.post(HEALTH, json={"run": run}).json()["data"]
    b = client.post(HEALTH, json={"run": run}).json()["data"]
    assert a == b
    assert a["findings"] == []  # telemetry equals the nominal model: residual 0 everywhere

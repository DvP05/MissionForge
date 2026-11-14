"""POST /api/mission/dossier (Task 4.6): export, re-import, replay chain (AC-13 / AC-22)."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_clock
from app.main import create_app

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
DOSSIER = "/api/mission/dossier"


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_clock] = lambda: lambda: NOW
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _run(client: TestClient, title: str | None = None) -> dict[str, Any]:
    state: dict[str, Any] = client.get("/api/templates/neo-rendezvous/default-mission").json()[
        "data"
    ]
    state["architecture"]["communicationsId"] = "comms-xband-medium"
    if title is not None:
        state["title"] = title
    r = client.post("/api/mission/simulate", json={"missionState": state, "randomSeed": 42})
    run: dict[str, Any] = r.json()["data"]["run"]
    return run


def test_dossier_returns_validated_package_and_html(client: TestClient) -> None:
    run = _run(client)
    r = client.post(DOSSIER, json={"run": run})
    body = r.json()
    assert r.status_code == 200 and body["ok"] is True
    data = body["data"]
    assert set(data) == {"package", "html", "replayStatus", "replayMismatches"}
    pkg = data["package"]
    assert pkg["packageSchemaVersion"] == "1.0" and pkg["exportedAt"].startswith("2026-11-14T12")
    assert pkg["runs"] == [run] and pkg["mission"] == run["inputSnapshot"]
    assert pkg["manifest"]["appVersion"] == "0.1.0"
    assert pkg["evidence"] and pkg["latestAnalysis"] is not None
    assert data["html"].startswith("<!doctype html>")
    assert "identical replay" in data["html"].lower()  # the server verified the replay


def test_exported_json_reimports_replayable_and_replays_identically(client: TestClient) -> None:
    run = _run(client)
    pkg = client.post(DOSSIER, json={"run": run}).json()["data"]["package"]
    imported = client.post(
        "/api/mission/import", content=json.dumps(pkg), headers={"Content-Type": "application/json"}
    ).json()
    assert imported["ok"] is True, imported
    [status] = imported["data"]["replay"]
    assert status["status"] == "replayable" and status["mismatches"] == []
    assert imported["data"]["package"]["mission"] == pkg["mission"]
    replay = client.post(
        "/api/mission/replay", json={"run": imported["data"]["package"]["runs"][0]}
    )
    assert replay.json()["data"]["identical"] is True


def test_dossier_is_deterministic_for_same_run_and_clock(client: TestClient) -> None:
    run = _run(client)
    a = client.post(DOSSIER, json={"run": run}).json()["data"]
    b = client.post(DOSSIER, json={"run": run}).json()["data"]
    assert a == b


def test_title_script_is_escaped_in_html(client: TestClient) -> None:
    run = _run(client, title="<script>alert(1)</script>")
    html = client.post(DOSSIER, json={"run": run}).json()["data"]["html"]
    assert "<script>" not in html and "alert(1)" in html


def test_tampered_run_is_exported_but_not_called_identical(client: TestClient) -> None:
    run = _run(client)
    run["telemetry"][0]["value"] = run["telemetry"][0]["value"] + 1.0
    html = client.post(DOSSIER, json={"run": run}).json()["data"]["html"]
    assert "not an identical replay" in html and "diverged" in html


def test_version_mismatch_is_reported_in_the_passport(client: TestClient) -> None:
    run = _run(client)
    run["engineVersion"] = "9.9.9"
    run["manifest"]["engineVersion"] = "9.9.9"
    d = client.post(DOSSIER, json={"run": run}).json()["data"]
    assert "not an identical replay" in d["html"] and "engineVersion" in d["html"]
    assert d["package"]["runs"][0]["manifest"]["engineVersion"] == "9.9.9"


def test_invalid_run_is_rejected_without_echo(client: TestClient) -> None:
    run = _run(client)
    run["seed"] = 7  # inconsistent with the manifest
    r = client.post(DOSSIER, json={"run": run})
    assert r.status_code == 422 and r.json()["ok"] is False
    assert client.post(DOSSIER, json={}).status_code == 422
    assert client.post(DOSSIER, json={"run": run, "extra": 1}).status_code == 422


def test_run_with_unknown_component_still_exports_with_label(client: TestClient) -> None:
    run = _run(client)
    run["inputSnapshot"]["architecture"]["busId"] = "bus-nope"
    r = client.post(DOSSIER, json={"run": run})
    assert r.status_code == 200
    d = r.json()["data"]
    assert "Budgets were not available" in d["html"]
    assert any(e["fidelity"] == "not-modelled" for e in d["package"]["evidence"])


def test_replay_status_is_structured(client: TestClient) -> None:
    run = _run(client)
    ok = client.post(DOSSIER, json={"run": run}).json()["data"]
    assert ok["replayStatus"] == "identical-replay" and ok["replayMismatches"] == []
    run["telemetry"][0]["value"] += 1.0
    bad = client.post(DOSSIER, json={"run": run}).json()["data"]
    assert bad["replayStatus"] == "diverged" and bad["replayMismatches"] == ["output"]


def test_spoofed_title_does_not_change_replay_status(client: TestClient) -> None:
    run = _run(client, title="Probe (identical replay)")
    run["telemetry"][0]["value"] += 1.0
    d = client.post(DOSSIER, json={"run": run}).json()["data"]
    assert d["replayStatus"] == "diverged"


def test_export_time_varies_only_exported_at_and_calculated_at() -> None:
    run_body: dict[str, Any] = {}
    outs = []
    for hour in (12, 18):
        app = create_app()
        t = datetime(2026, 11, 14, hour, tzinfo=UTC)
        app.dependency_overrides[get_clock] = lambda t=t: lambda: t
        with TestClient(app) as c:
            if not run_body:
                run_body["run"] = _run(c)
            outs.append(c.post(DOSSIER, json=run_body).json()["data"])
    a, b = outs
    for d, hr in ((a, 12), (b, 18)):
        d["package"]["exportedAt"] = "X"
        d["package"]["latestAnalysis"]["calculatedAt"] = "X"
        d["html"] = d["html"].replace(f"2026-11-14T{hr}:00:00Z", "X")
    assert a == b

"""Catalogue / templates / validate routes, the error envelope and the payload limit (Task 3.1)."""

import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_clock
from app.main import create_app

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
ORIGIN = {"Origin": "http://localhost:3000"}
JSON = {"Content-Type": "application/json"}


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_clock] = lambda: lambda: NOW
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _default(client: TestClient, scenario: str = "neo-rendezvous") -> dict[str, Any]:
    r = client.get(f"/api/templates/{scenario}/default-mission")
    assert r.status_code == 200
    state: dict[str, Any] = r.json()["data"]
    return state


def _validate(client: TestClient, state: dict[str, Any], **kwargs: Any) -> Any:
    return client.post("/api/mission/validate", json={"missionState": state}, **kwargs)


# --- catalogue / templates -------------------------------------------------------------


def test_catalog_groups_by_category(client: TestClient) -> None:
    r = client.get("/api/catalog")
    body = r.json()
    assert r.status_code == 200 and body["ok"] is True
    data = body["data"]
    assert data["catalogVersion"] == "0.1.0"
    cats = {g["category"] for g in data["groups"]}
    assert {"launch", "bus", "propulsion", "power", "instrument", "ground"} <= cats
    assert all(g["components"] for g in data["groups"])
    assert data["sources"] and all("sourceName" in s for s in data["sources"])
    assert body["meta"]["requestId"] == r.headers["x-request-id"]


def test_templates_lists_all_scenarios(client: TestClient) -> None:
    body = client.get("/api/templates").json()
    assert body["ok"] is True
    ids = [t["scenarioId"] for t in body["data"]]
    assert ids == ["earth-observation", "lunar-polar-scout", "neo-rendezvous"]
    assert all(t["fidelityNotes"] and t["topConstraints"] for t in body["data"])


def test_default_mission_is_fresh_and_uses_clock(client: TestClient) -> None:
    a = _default(client)
    b = client.get("/api/templates/neo-rendezvous/default-mission?seed=7").json()["data"]
    assert a["missionId"] != b["missionId"]
    assert a["randomSeed"] == 42 and b["randomSeed"] == 7
    assert a["designRevision"] == 0
    assert a["createdAt"].startswith("2026-11-13T12:00:00")


def test_default_mission_unknown_scenario_is_enveloped_404(client: TestClient) -> None:
    r = client.get("/api/templates/nope/default-mission", headers=ORIGIN)
    assert r.status_code == 404
    assert r.json()["ok"] is False and r.json()["error"]["code"] == "NOT_FOUND"
    assert r.headers["access-control-allow-origin"] == ORIGIN["Origin"]


def test_default_mission_bad_seed_is_validation_error(client: TestClient) -> None:
    r = client.get("/api/templates/neo-rendezvous/default-mission?seed=-1")
    assert r.status_code == 422
    paths = {f["path"] for f in r.json()["error"]["details"]["fields"]}
    assert "query.seed" in paths


# --- validate -------------------------------------------------------------------------


@pytest.mark.parametrize("scenario", ["neo-rendezvous", "lunar-polar-scout", "earth-observation"])
def test_validate_default_returns_analysis(client: TestClient, scenario: str) -> None:
    state = _default(client, scenario)
    state["designRevision"] = 5
    r = _validate(client, state)
    body = r.json()
    assert r.status_code == 200 and body["ok"] is True
    analysis = body["data"]["analysis"]
    assert analysis["designRevision"] == 5
    assert analysis["missionId"] == state["missionId"]
    assert analysis["calculatedAt"].startswith("2026-11-13T12:00:00")
    assert analysis["engineVersion"] == "0.1.0" and analysis["catalogVersion"] == "0.1.0"
    assert analysis["feasibility"] in {"feasible", "marginal", "infeasible"}


def test_validate_is_deterministic(client: TestClient) -> None:
    state = _default(client)
    first = _validate(client, state).json()["data"]["analysis"]
    second = _validate(client, state).json()["data"]["analysis"]
    first.pop("calculatedAt")
    second.pop("calculatedAt")
    assert first == second


def test_validate_bad_body_reports_field_paths(client: TestClient) -> None:
    state = _default(client)
    del state["architecture"]["busId"]
    state["designRevision"] = -1
    r = _validate(client, state)
    body = r.json()
    assert r.status_code == 422 and body["ok"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR" and body["error"]["retryable"] is False
    paths = {f["path"] for f in body["error"]["details"]["fields"]}
    assert "missionState.architecture.busId" in paths
    assert "missionState.designRevision" in paths


def test_validate_invalid_json_and_missing_body(client: TestClient) -> None:
    r = client.post("/api/mission/validate", content=b"{not json", headers=JSON)
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    r2 = client.post("/api/mission/validate", json={})
    assert r2.status_code == 422
    assert r2.json()["error"]["details"]["fields"][0]["path"] == "missionState"


def test_validate_rejects_nan_literal(client: TestClient) -> None:
    state = _default(client)
    raw = re.sub(
        r'"maximumBudgetUsd": [^,}]+',
        '"maximumBudgetUsd": NaN',
        json.dumps({"missionState": state}),
    )
    assert "NaN" in raw
    r = client.post("/api/mission/validate", content=raw.encode(), headers=JSON)
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    paths = {f["path"] for f in r.json()["error"]["details"]["fields"]}
    assert "missionState.constraints.maximumBudgetUsd" in paths


def test_validate_unknown_component_is_catalog_item_not_found(client: TestClient) -> None:
    state = _default(client)
    state["architecture"]["busId"] = "bus-does-not-exist"
    state["architecture"]["instrumentIds"] = [*state["architecture"]["instrumentIds"], "inst-zzz"]
    r = _validate(client, state)
    body = r.json()
    assert r.status_code == 422 and body["ok"] is False
    assert body["error"]["code"] == "CATALOG_ITEM_NOT_FOUND"
    items = body["error"]["details"]["items"]
    assert {"path": "architecture.busId", "id": "bus-does-not-exist"} in items
    assert any(i["id"] == "inst-zzz" and "instrumentIds[" in i["path"] for i in items)


def test_validate_other_issues_are_validation_error(client: TestClient) -> None:
    state = _default(client)
    state["architecture"]["instrumentIds"] = [state["architecture"]["instrumentIds"][0]] * 2
    body = _validate(client, state).json()
    assert body["ok"] is False and body["error"]["code"] == "VALIDATION_ERROR"
    issues = body["error"]["details"]["issues"]
    assert any(i["code"] == "DUPLICATE_ID" for i in issues)


def test_infeasible_design_is_still_ok_true(client: TestClient) -> None:
    state = _default(client)
    state["constraints"]["launchMassLimitKg"] = 1.0
    r = _validate(client, state)
    body = r.json()
    assert r.status_code == 200 and body["ok"] is True
    assert body["data"]["analysis"]["feasibility"] == "infeasible"
    assert body["data"]["analysis"]["missionReady"] is False


def test_html_title_is_sanitised_before_echo(client: TestClient) -> None:
    state = _default(client)
    state["title"] = "<script>alert(1)</script>Rendezvous <b>One</b>"
    r = _validate(client, state)
    assert r.status_code == 200
    assert "<script" not in r.text and "<b>" not in r.text


# --- payload limit --------------------------------------------------------------------


def test_oversized_body_with_content_length_is_413(client: TestClient) -> None:
    big = b'{"missionState": "' + b"x" * (300 * 1024) + b'"}'
    r = client.post("/api/mission/validate", content=big, headers={**JSON, **ORIGIN})
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert r.json()["ok"] is False
    assert r.headers["access-control-allow-origin"] == ORIGIN["Origin"]


def test_oversized_chunked_body_is_413(client: TestClient) -> None:
    def chunks() -> Iterator[bytes]:
        yield b'{"missionState": "'
        for _ in range(40):
            yield b"x" * 8192
        yield b'"}'

    r = client.post("/api/mission/validate", content=chunks(), headers=JSON)
    assert r.status_code == 413 and r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_normal_body_is_accepted(client: TestClient) -> None:
    assert _validate(client, _default(client)).status_code == 200


# --- error envelope / CORS ------------------------------------------------------------


def test_unknown_route_and_wrong_method_use_envelope(client: TestClient) -> None:
    nf = client.get("/api/nothing-here", headers=ORIGIN)
    assert nf.status_code == 404
    assert nf.json()["error"]["code"] == "NOT_FOUND" and nf.json()["meta"]["requestId"]
    assert nf.headers["access-control-allow-origin"] == ORIGIN["Origin"]
    bad = client.get("/api/mission/validate", headers=ORIGIN)
    assert bad.status_code == 405
    assert bad.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert "POST" in bad.headers["allow"]


def test_validation_error_carries_cors(client: TestClient) -> None:
    r = client.post("/api/mission/validate", json={}, headers=ORIGIN)
    assert r.status_code == 422
    assert r.headers["access-control-allow-origin"] == ORIGIN["Origin"]
    assert r.headers["x-request-id"] == r.json()["meta"]["requestId"]


def test_unexpected_error_hides_detail_and_carries_cors(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.mission_service import MissionService

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("secret-internal-detail")

    monkeypatch.setattr(MissionService, "validate", boom)
    r = _validate(client, _default(client), headers=ORIGIN)
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "secret-internal-detail" not in r.text and "Traceback" not in r.text
    assert r.json()["meta"]["requestId"] == r.headers["x-request-id"]
    assert r.headers["access-control-allow-origin"] == ORIGIN["Origin"]


def test_error_cors_not_granted_to_foreign_origin(client: TestClient) -> None:
    r = client.get("/api/nothing-here", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in r.headers

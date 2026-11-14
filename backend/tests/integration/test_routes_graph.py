"""POST /api/mission/graph and /api/mission/impact (Task 6.1)."""

import copy
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_clock
from app.main import create_app

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_clock] = lambda: lambda: NOW
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _default(client: TestClient) -> dict[str, Any]:
    data: dict[str, Any] = client.get("/api/templates/neo-rendezvous/default-mission").json()[
        "data"
    ]
    return data


def test_graph_route_returns_graph_and_matrices(client: TestClient) -> None:
    state = _default(client)
    r = client.post("/api/mission/graph", json={"missionState": state})
    body = r.json()
    assert r.status_code == 200 and body["ok"] is True
    data = body["data"]
    assert data["designRevision"] == state["designRevision"]
    assert data["missionId"] == state["missionId"]
    ids = {n["id"] for n in data["graph"]["nodes"]}
    assert "objective:obj-composition" in ids
    assert all(e["fromId"] in ids and e["toId"] in ids for e in data["graph"]["edges"])
    assert {row["requirementId"] for row in data["scienceTraceability"]} >= {"meas-vnir-spectra"}
    assert [row["instrumentId"] for row in data["missionTraceability"]] == state["architecture"][
        "instrumentIds"
    ]
    assert body["meta"]["requestId"]


def test_impact_route_explains_antenna_swap(client: TestClient) -> None:
    before = _default(client)
    after = copy.deepcopy(before)
    after["architecture"]["communicationsId"] = "comms-xband-medium"
    after["designRevision"] = before["designRevision"] + 1
    r = client.post(
        "/api/mission/impact", json={"beforeMissionState": before, "afterMissionState": after}
    )
    body = r.json()
    assert r.status_code == 200 and body["ok"] is True
    data = body["data"]
    assert (data["beforeRevision"], data["afterRevision"]) == (0, 1) or data["afterRevision"] == (
        data["beforeRevision"] + 1
    )
    assert "link-margin" in data["impact"]["improved"]
    assert any(m["metric"] == "dataDownlinkedBits" for m in data["impact"]["changedMetrics"])
    assert any(n["entityId"] == "comms-xband-medium" for n in data["graph"]["nodes"])


def test_unknown_component_maps_to_catalog_error(client: TestClient) -> None:
    state = _default(client)
    state["architecture"]["communicationsId"] = "comms-does-not-exist"
    r = client.post("/api/mission/graph", json={"missionState": state})
    body = r.json()
    assert r.status_code == 422 and body["ok"] is False
    assert body["error"]["code"] == "CATALOG_ITEM_NOT_FOUND"

    good = _default(client)
    r = client.post(
        "/api/mission/impact", json={"beforeMissionState": good, "afterMissionState": state}
    )
    body = r.json()
    assert r.status_code == 422 and body["error"]["code"] == "CATALOG_ITEM_NOT_FOUND"
    assert body["error"]["details"]["design"]["role"] == "alternative"


def test_bad_body_is_validation_error(client: TestClient) -> None:
    r = client.post("/api/mission/graph", json={"missionState": {"title": "x"}})
    body = r.json()
    assert r.status_code == 422 and body["ok"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "Traceback" not in r.text


def test_graph_route_is_fast(client: TestClient) -> None:
    state = _default(client)
    client.post("/api/mission/graph", json={"missionState": state})  # warm up
    start = time.perf_counter()
    for _ in range(10):
        assert client.post("/api/mission/graph", json={"missionState": state}).status_code == 200
    assert (time.perf_counter() - start) / 10 < 0.3

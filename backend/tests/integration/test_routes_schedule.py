"""POST /api/mission/schedule (Task 6.6)."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        yield c


def _default(client: TestClient) -> dict[str, Any]:
    data: dict[str, Any] = client.get("/api/templates/neo-rendezvous/default-mission").json()[
        "data"
    ]
    return data


def test_schedule_route(client: TestClient) -> None:
    state = _default(client)
    body = client.post("/api/mission/schedule", json={"missionState": state}).json()
    assert body["ok"] is True
    data = body["data"]
    assert data["algorithm"].startswith("Greedy heuristic")
    ids = {o["id"] for o in data["opportunities"]}
    assert set(data["schedule"]["accepted"]) <= ids
    assert all(data["measurementOf"][a] for a in data["schedule"]["accepted"])
    assert all(p["bits"] <= data["bufferCapacityBits"] for p in data["schedule"]["bufferTimeline"])


def test_schedule_unknown_component(client: TestClient) -> None:
    state = _default(client)
    state["architecture"]["cdhId"] = "cdh-nope"
    r = client.post("/api/mission/schedule", json={"missionState": state})
    assert r.status_code == 422 and r.json()["error"]["code"] == "CATALOG_ITEM_NOT_FOUND"

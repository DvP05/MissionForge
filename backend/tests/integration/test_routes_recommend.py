"""POST /api/mission/recommend (Task 6.8)."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_clock
from app.main import create_app

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
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


def test_recommend_route(client: TestClient) -> None:
    state = _default(client)
    body = client.post("/api/mission/recommend", json={"missionState": state}).json()
    assert body["ok"] is True
    data = body["data"]
    assert data["designRevision"] == state["designRevision"]
    top = data["recommendations"][0]
    assert top["mutation"]["toValue"].startswith("comms-")
    assert "link-margin" in data["explanations"]


def test_recommend_limits(client: TestClient) -> None:
    r = client.post("/api/mission/recommend", json={"missionState": _default(client), "maxN": 9})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"

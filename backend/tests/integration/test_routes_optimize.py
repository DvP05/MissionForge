"""POST /api/mission/optimize (Task 6.2)."""

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


def test_optimize_returns_compact_summaries(client: TestClient) -> None:
    state = _default(client)
    r = client.post(
        "/api/mission/optimize", json={"missionState": state, "cap": 60, "robustnessSamples": 5}
    )
    body = r.json()
    assert r.status_code == 200 and body["ok"] is True
    data = body["data"]
    assert data["seed"] == state["randomSeed"]
    assert len(data["candidates"]) == 60
    ids = {c["id"] for c in data["candidates"]}
    assert set(data["paretoFrontIds"]) <= ids and set(data["nearMisses"]) <= ids
    assert set(data["archetypes"]) <= {"lean", "science-max", "resilient"}
    first = data["candidates"][0]
    assert first["architecture"] == state["architecture"]
    assert "missionState" not in first and "analysis" not in first
    assert len(r.content) < 400_000


def test_cap_and_samples_limits(client: TestClient) -> None:
    state = _default(client)
    for extra in ({"cap": 251}, {"cap": 5}, {"robustnessSamples": 51}):
        r = client.post("/api/mission/optimize", json={"missionState": state, **extra})
        assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"

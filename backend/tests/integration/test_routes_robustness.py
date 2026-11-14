"""POST /api/mission/robustness (Task 6.3)."""

import copy
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


def test_robustness_route_defaults_and_determinism(client: TestClient) -> None:
    state = _default(client)
    state["architecture"]["communicationsId"] = "comms-xband-medium"
    body = {"missionState": state, "samples": 30}
    first = client.post("/api/mission/robustness", json=body).json()
    second = client.post("/api/mission/robustness", json=copy.deepcopy(body)).json()
    assert first["ok"] is True
    result = first["data"]["result"]
    assert result["samples"] == 30 and result["seed"] == state["randomSeed"]
    assert len(result["feasibilityWilson95"]) == 2
    assert result["disclaimer"]
    assert first["data"] == second["data"]


def test_too_many_samples_is_limit_error(client: TestClient) -> None:
    r = client.post(
        "/api/mission/robustness", json={"missionState": _default(client), "samples": 5000}
    )
    body = r.json()
    assert r.status_code == 422 and body["error"]["code"] == "SIMULATION_LIMIT_EXCEEDED"


def test_zero_samples_is_validation_error(client: TestClient) -> None:
    r = client.post(
        "/api/mission/robustness", json={"missionState": _default(client), "samples": 0}
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unknown_component_maps_to_catalog_error(client: TestClient) -> None:
    state = _default(client)
    state["architecture"]["powerId"] = "power-nope"
    r = client.post("/api/mission/robustness", json={"missionState": state, "samples": 5})
    assert r.status_code == 422 and r.json()["error"]["code"] == "CATALOG_ITEM_NOT_FOUND"

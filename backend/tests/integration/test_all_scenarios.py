"""Task 7.1: every scenario analyses, simulates, replays deterministically and exports."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

SCENARIOS = ["neo-rendezvous", "lunar-polar-scout", "earth-observation"]


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        yield c


def _state(client: TestClient, scenario: str) -> dict[str, Any]:
    body = client.get(f"/api/templates/{scenario}/default-mission").json()
    assert body["ok"] is True, body
    state: dict[str, Any] = body["data"]
    return state


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_scenario_full_chain(client: TestClient, scenario: str) -> None:
    state = _state(client, scenario)
    analysis = client.post("/api/mission/validate", json={"missionState": state}).json()
    assert analysis["ok"] is True, analysis
    # starters teach a trade but are launchable (NEO needs the medium radio first)
    if scenario == "neo-rendezvous":
        state["architecture"]["communicationsId"] = "comms-xband-medium"
    sim = client.post("/api/mission/simulate", json={"missionState": state, "randomSeed": 7}).json()
    assert sim["ok"] is True, sim
    run = sim["data"]["run"]
    assert len(run["phases"]) >= 6 or run["finalReport"]["outcome"] == "terminated"
    assert sum(e["type"] == "decision" for e in run["events"]) >= 2  # AC-10
    assert run["autonomyLog"]  # Phase 6 joined to every scenario
    replay = client.post("/api/mission/replay", json={"run": run}).json()["data"]
    assert replay["identical"] is True and replay["status"] == "identical-replay"
    again = client.post(
        "/api/mission/simulate", json={"missionState": state, "randomSeed": 7}
    ).json()["data"]["run"]
    assert again == run
    dossier = client.post("/api/mission/dossier", json={"run": run}).json()
    assert dossier["ok"] is True and dossier["data"]["replayStatus"] == "identical-replay"

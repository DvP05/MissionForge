"""Space-data routes and JPL provenance in the passport (Task 5.3, R48). No network (R6)."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.integrations.jpl.client import JplClient, user_agent
from app.integrations.jpl.repository import JplRepository, Snapshot
from app.main import create_app

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "jpl"
MODE_A = json.loads((FIX / "mode_a_ok.json").read_text(encoding="utf-8"))
RAW_KEYS = ("fields", "records", "signature", "c3_dep", "vinf_dep", "dv_tot", "pdes", "full_name")


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        yield c


def _no_raw_keys(obj: Any) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert k not in RAW_KEYS, k
            _no_raw_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            _no_raw_keys(v)


def test_offline_by_default_serves_labelled_synthetic_snapshot(client: TestClient) -> None:
    body = client.get("/api/space-data/neo-accessible?years=2031&criterion=1&limit=20").json()
    assert body["ok"] is True
    assert body["meta"]["sourceStatus"] == "demo"
    src = body["data"]["source"]
    assert src["status"] == "demo" and src["synthetic"] is True and "not JPL data" in src["note"]
    opts = body["data"]["options"]
    assert opts and {o["source"]["fidelity"] for o in opts} == {"gameplay-estimate"}
    _no_raw_keys(body["data"])
    assert client.get("/api/health").json()["data"]["jplAdapter"]["status"] == "demo"


def test_detail_known_unknown_and_invalid(client: TestClient) -> None:
    ok = client.get("/api/space-data/neo/2031 SY1").json()
    assert ok["ok"] is True and ok["data"]["options"]
    _no_raw_keys(ok["data"])
    missing = client.get("/api/space-data/neo/2099 ZZ9")
    assert missing.status_code == 503 and missing.json()["error"]["code"] == "JPL_UNAVAILABLE"
    bad = client.get("/api/space-data/neo/%22%3B%20rm%20-rf")
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "query", ["years=1999", "years=2031&criterion=9", "years=2031&limit=500", "years=abc"]
)
def test_search_params_are_allow_listed(client: TestClient, query: str) -> None:
    r = client.get(f"/api/space-data/neo-accessible?{query}")
    assert r.status_code == 422 and r.json()["ok"] is False


def _picked_state(client: TestClient, option: dict[str, Any]) -> dict[str, Any]:
    state: dict[str, Any] = client.get("/api/templates/neo-rendezvous/default-mission").json()[
        "data"
    ]
    state["architecture"]["communicationsId"] = "comms-xband-medium"
    state["trajectory"] = {
        "provider": "jpl-mdesign",
        "optionId": option["designation"],
        "departureDate": option["departureDate"],
        "arrivalDate": option["arrivalDate"],
        "timeOfFlightDays": option["timeOfFlightDays"],
        "c3Km2PerS2": option["c3Km2PerS2"],
        "departureVInfinityKmPerS": option["departureVInfinityKmPerS"],
        "arrivalVInfinityKmPerS": option["arrivalVInfinityKmPerS"],
        "missionDeltaVKmPerS": option["totalDeltaVKmPerS"],
        "rawSourceRef": option["sourceRef"],
    }
    return state


def _trajectory_records(client: TestClient, state: dict[str, Any]) -> list[dict[str, Any]]:
    run = client.post("/api/mission/simulate", json={"missionState": state, "randomSeed": 1}).json()
    assert run["ok"], run
    pkg = client.post("/api/mission/dossier", json={"run": run["data"]["run"]}).json()["data"]
    return [e for e in pkg["package"]["evidence"] if e["subjectId"].startswith("trajectory.")]


def test_picked_synthetic_option_is_verified_but_never_source_backed(client: TestClient) -> None:
    option = client.get("/api/space-data/neo-accessible?years=2031").json()["data"]["options"][0]
    state = _picked_state(client, option)
    analysis = client.post("/api/mission/validate", json={"missionState": state}).json()
    # C3 is launch energy, never spacecraft delta-v (AC-08/AC-09, R41)
    dv = analysis["data"]["analysis"]["budgets"]["requiredDeltaVKmPerS"]["value"]
    assert dv == pytest.approx(0.25)
    recs = _trajectory_records(client, state)
    assert recs and {r["fidelity"] for r in recs} == {"gameplay-estimate"}
    assert all("NOT JPL data" in r["sourceTitle"] for r in recs)


def test_forged_reference_stays_claimed(client: TestClient) -> None:
    option = client.get("/api/space-data/neo-accessible?years=2031").json()["data"]["options"][0]
    state = _picked_state(client, {**option, "c3Km2PerS2": 1.0})
    recs = _trajectory_records(client, state)
    assert {r["fidelity"] for r in recs} == {"gameplay-estimate"}
    assert all("unverified" in r["sourceTitle"].lower() for r in recs)


def test_live_verified_option_becomes_source_backed() -> None:
    app = create_app()
    app.state.jpl_repository = JplRepository(
        client=JplClient(
            "https://ssd-api.jpl.nasa.gov/mdesign.api",
            user_agent=user_agent("0.1.0", "team@example.org"),
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=MODE_A)),
        ),
        snapshot=Snapshot(synthetic=True, captured_at=None, note="", mode_a=[], mode_q={}),
        live_enabled=True,
    )
    with TestClient(app) as c:
        body = c.get("/api/space-data/neo-accessible?years=2031").json()
        assert body["meta"]["sourceStatus"] == "live"
        option = body["data"]["options"][0]
        assert option["source"]["fidelity"] == "source-backed"
        recs = _trajectory_records(c, _picked_state(c, option))
    assert {r["fidelity"] for r in recs} == {"source-backed"}
    assert all(r["sourceUrl"] == "https://ssd-api.jpl.nasa.gov/mdesign.api" for r in recs)
    assert all(r["retrievedAt"] for r in recs)

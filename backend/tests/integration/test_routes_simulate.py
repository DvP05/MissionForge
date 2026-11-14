"""POST /api/mission/simulate, POST/GET /api/mission/run/{runId}... (Task 4.3, R32)."""

import json
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_clock
from app.main import create_app
from app.services.simulation_service import RunStore, SimulationService

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
SIM = "/api/mission/simulate"
SOLAR = "scenario-solar-event"


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_clock] = lambda: lambda: NOW
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _state(client: TestClient, scenario: str = "neo-rendezvous", **arch: Any) -> dict[str, Any]:
    state: dict[str, Any] = client.get(f"/api/templates/{scenario}/default-mission").json()["data"]
    state["architecture"].update(arch)
    return state


def _sim(client: TestClient, state: dict[str, Any], **extra: Any) -> Any:
    return client.post(SIM, json={"missionState": state, "randomSeed": 42, **extra})


def _medium(client: TestClient) -> dict[str, Any]:
    return _state(client, communicationsId="comms-xband-medium")


def _decide(client: TestClient, run_id: str, event: str, choice: str) -> Any:
    return client.post(
        f"/api/mission/run/{run_id}/decision", json={"eventId": event, "choiceId": choice}
    )


def test_returns_spec_shape_with_exact_references(client: TestClient) -> None:
    r = _sim(client, _medium(client))
    body = r.json()
    assert r.status_code == 200 and body["ok"] is True
    d = body["data"]
    assert set(d) >= {"analysis", "run", "telemetry", "events", "finalReport"}
    assert d["telemetry"] == d["run"]["telemetry"]
    assert d["events"] == d["run"]["events"]
    assert d["finalReport"] == d["run"]["finalReport"]
    assert d["run"]["scenarioEventSetId"] == "neo-default-v1"  # default for the scenario
    assert d["run"]["manifest"]["scenarioVersion"] and d["run"]["manifest"]["appVersion"]
    assert d["run"]["seed"] == 42


def test_analysis_is_computed_by_the_server(client: TestClient) -> None:
    state = _medium(client)
    validated = client.post("/api/mission/validate", json={"missionState": state}).json()
    r = _sim(client, state)
    assert r.json()["data"]["analysis"] == validated["data"]["analysis"]
    r = client.post(SIM, json={"missionState": state, "randomSeed": 1, "analysis": {}})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_same_request_twice_is_identical(client: TestClient) -> None:
    state = _medium(client)
    a, b = _sim(client, state), _sim(client, state)
    assert a.json()["data"] == b.json()["data"]
    assert json.dumps(a.json()["data"]["run"], sort_keys=True) == json.dumps(
        b.json()["data"]["run"], sort_keys=True
    )


def test_launch_blocked_lists_failing_constraints(client: TestClient) -> None:
    r = _sim(client, _state(client))  # lowgain starter is infeasible
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "LAUNCH_BLOCKED"
    assert "link-margin" in err["details"]["failingConstraintIds"]
    ok = _sim(client, _state(client), experimental=True)
    assert ok.status_code == 200 and ok.json()["data"]["run"]["experimental"] is True


def test_unknown_event_set_and_scenario_mismatch(client: TestClient) -> None:
    r = _sim(client, _medium(client), scenarioEventSetId="nope-v9")
    assert r.status_code == 422 and r.json()["error"]["code"] == "UNKNOWN_EVENT_SET"
    r = _sim(client, _medium(client), scenarioEventSetId="lunar-default-v1")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "EVENT_SET_SCENARIO_MISMATCH"
    r = _sim(client, _medium(client), scenarioEventSetId="nominal-v1")
    assert r.status_code == 200 and r.json()["data"]["run"]["scenarioEventSetId"] == "nominal-v1"


def test_other_scenarios_use_their_default_set(client: TestClient) -> None:
    for sid, expected in (
        ("lunar-polar-scout", "lunar-default-v1"),
        ("earth-observation", "eo-default-v1"),
    ):
        r = _sim(client, _state(client, sid), experimental=True)
        assert r.status_code == 200, r.text
        assert r.json()["data"]["run"]["scenarioEventSetId"] == expected


def test_monte_carlo_cap(client: TestClient) -> None:
    state = _medium(client)
    r = _sim(client, state, monteCarloSamples=1001)
    assert r.status_code == 422 and r.json()["error"]["code"] == "SIMULATION_LIMIT_EXCEEDED"
    assert r.json()["error"]["details"]["maxSamples"] == 1000
    ok = _sim(client, state, monteCarloSamples=250)
    assert ok.status_code == 200
    assert any("Monte Carlo" in n for n in ok.json()["data"]["notes"])
    assert _sim(client, state, monteCarloSamples=0).status_code == 422


def test_unknown_component_uses_validation_envelope(client: TestClient) -> None:
    state = _medium(client)
    state["architecture"]["powerId"] = "power-missing"
    r = _sim(client, state)
    assert r.status_code == 422 and r.json()["error"]["code"] == "CATALOG_ITEM_NOT_FOUND"


def test_payload_budget_enforced(client: TestClient) -> None:
    big = {"missionState": _medium(client), "randomSeed": 1, "pad": "x" * (300 * 1024)}
    r = client.post(SIM, json=big)
    assert r.status_code == 413 and r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_simulation_time_budget(client: TestClient) -> None:
    state = _medium(client)
    _sim(client, state)  # warm-up
    times = []
    for _ in range(10):
        t = time.perf_counter()
        assert _sim(client, state).status_code == 200
        times.append(time.perf_counter() - t)
    assert max(times) < 1.0, times


def test_decisions_in_request_are_applied_and_player_recorded(client: TestClient) -> None:
    state = _medium(client)
    r = _sim(client, state, decisions={SOLAR: "continue"})
    run = r.json()["data"]["run"]
    mine = [d for d in run["decisions"] if d["eventId"] == SOLAR]
    assert mine[0]["choiceId"] == "continue" and mine[0]["decisionMaker"] == "player"
    bad = _sim(client, state, decisions={SOLAR: "bogus"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "INVALID_CHOICE"
    unk = _sim(client, state, decisions={"no-such-event": "x"})
    assert unk.status_code == 422 and unk.json()["error"]["code"] == "UNKNOWN_DECISION_EVENT"


def test_decision_creates_new_run_and_leaves_source_unchanged(client: TestClient) -> None:
    first = _sim(client, _medium(client)).json()["data"]
    src_id = first["run"]["runId"]
    r = _decide(client, src_id, SOLAR, "continue")
    assert r.status_code == 200, r.text
    new = r.json()["data"]
    assert new["run"]["runId"] != src_id
    assert any(
        d["eventId"] == SOLAR and d["decisionMaker"] == "player" for d in new["run"]["decisions"]
    )
    assert set(new) >= {"analysis", "run", "telemetry", "events", "finalReport"}
    again = client.get(f"/api/mission/run/{src_id}").json()["data"]
    assert again["run"] == first["run"]
    assert client.get(f"/api/mission/run/{new['run']['runId']}").json()["data"]["run"] == new["run"]


def test_run_immutable_second_decision_on_same_event_rejected(client: TestClient) -> None:
    src = _sim(client, _medium(client)).json()["data"]["run"]["runId"]
    new_id = _decide(client, src, SOLAR, "continue").json()["data"]["run"]["runId"]
    r = _decide(client, new_id, SOLAR, "pause-science")
    assert r.status_code == 409 and r.json()["error"]["code"] == "DECISION_ALREADY_MADE"
    # the source run (where the event was only defaulted) can still be branched differently
    assert _decide(client, src, SOLAR, "pause-science").status_code == 200


def test_decision_chains_keep_earlier_choices(client: TestClient) -> None:
    src = _sim(client, _medium(client)).json()["data"]["run"]["runId"]
    a = _decide(client, src, SOLAR, "continue").json()["data"]["run"]["runId"]
    b = _decide(client, a, "scenario-target-illumination", "extend-observation")
    assert b.status_code == 200
    made = {
        d["eventId"]: d["choiceId"]
        for d in b.json()["data"]["run"]["decisions"]
        if d["decisionMaker"] == "player"
    }
    assert made == {SOLAR: "continue", "scenario-target-illumination": "extend-observation"}


def test_decision_errors(client: TestClient) -> None:
    run_id = _sim(client, _medium(client)).json()["data"]["run"]["runId"]
    r = _decide(client, "run-doesnotexist", SOLAR, "continue")
    assert r.status_code == 404 and r.json()["error"]["code"] == "RUN_NOT_FOUND"
    r = _decide(client, run_id, "no-such-event", "continue")
    assert r.status_code == 422 and r.json()["error"]["code"] == "UNKNOWN_DECISION_EVENT"
    r = _decide(client, run_id, SOLAR, "bogus")
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_CHOICE"
    r = client.post(f"/api/mission/run/{run_id}/decision", json={"eventId": "x"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    missing = client.get("/api/mission/run/run-doesnotexist")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "RUN_NOT_FOUND"


def test_decision_after_termination_rejected(client: TestClient) -> None:
    state = _state(client, propulsionId="prop-cold-gas", communicationsId="comms-xband-medium")
    r = _sim(client, state, experimental=True)
    assert r.status_code == 200, r.text
    run = r.json()["data"]["run"]
    assert "anomaly-correction-shortfall" in [e["id"] for e in run["events"] if e["choices"]]
    t = _decide(client, run["runId"], "anomaly-correction-shortfall", "abort-mission")
    assert t.status_code == 200
    assert t.json()["data"]["run"]["finalReport"]["outcome"] == "terminated"
    later = _decide(client, t.json()["data"]["run"]["runId"], SOLAR, "continue")
    assert later.status_code == 422 and later.json()["error"]["code"] == "UNKNOWN_DECISION_EVENT"


def test_branching_earlier_ending_choice_prunes_cancelled_later_decisions(
    client: TestClient,
) -> None:
    state = _state(client, propulsionId="prop-cold-gas", communicationsId="comms-xband-medium")
    src = _sim(client, state, experimental=True).json()["data"]["run"]["runId"]
    a = _decide(client, src, SOLAR, "continue")  # later event decided first
    assert a.status_code == 200
    b = _decide(
        client, a.json()["data"]["run"]["runId"], "anomaly-correction-shortfall", "abort-mission"
    )
    assert b.status_code == 200, b.text
    run = b.json()["data"]["run"]
    assert run["finalReport"]["outcome"] == "terminated"
    assert SOLAR not in [d["eventId"] for d in run["decisions"]]
    assert SOLAR not in [e["id"] for e in run["events"]]
    # the newly supplied event is still strictly validated
    t = _decide(client, run["runId"], SOLAR, "continue")
    assert t.status_code == 422 and t.json()["error"]["code"] == "UNKNOWN_DECISION_EVENT"


def test_request_bounds_on_event_set_and_decisions(client: TestClient) -> None:
    state = _medium(client)
    r = _sim(client, state, scenarioEventSetId="")
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    r = _sim(client, state, decisions={"k" * 201: "x"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    r = _sim(client, state, decisions={SOLAR: "v" * 201})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    r = _sim(client, state, decisions={SOLAR: ""})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_evicted_run_returns_404(client: TestClient) -> None:
    app = client.app
    old = app.state.simulation_service  # type: ignore[attr-defined]
    app.state.simulation_service = SimulationService(  # type: ignore[attr-defined]
        old._missions,
        old._catalog,
        old._templates,
        old._event_sets,  # noqa: SLF001
        engine_version=old._engine_version,
        app_version=old._app_version,  # noqa: SLF001
        store=RunStore(capacity=2),
    )
    state = _medium(client)
    ids = [
        _sim(client, state, scenarioEventSetId=es).json()["data"]["run"]["runId"]
        for es in ("nominal-v1", "neo-default-v1", "generic-design-v1")
    ]
    assert len(set(ids)) == 3
    gone = client.get(f"/api/mission/run/{ids[0]}")
    assert gone.status_code == 404 and gone.json()["error"]["code"] == "RUN_NOT_FOUND"
    assert _decide(client, ids[0], SOLAR, "continue").status_code == 404
    assert client.get(f"/api/mission/run/{ids[2]}").status_code == 200

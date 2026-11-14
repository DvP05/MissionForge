"""POST /api/science/belief (Task 6.4)."""

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.domain.science_belief import hidden_truth
from app.main import create_app
from app.services.science_service import load_science_models


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        yield c


def _default(client: TestClient, scenario: str = "neo-rendezvous") -> dict[str, Any]:
    data: dict[str, Any] = client.get(f"/api/templates/{scenario}/default-mission").json()["data"]
    return data


def test_prior_then_observe_then_replay(client: TestClient) -> None:
    state = _default(client)
    prior = client.post("/api/science/belief", json={"missionState": state}).json()["data"]
    assert prior["belief"]["version"] == 0
    assert prior["nextObservations"], "selected instruments are ranked"
    assert prior["disclaimer"].startswith("Conditional on the scenario model")
    first = prior["nextObservations"][0]["instrumentId"]

    observed = client.post(
        "/api/science/belief", json={"missionState": state, "observeWith": first}
    ).json()["data"]
    assert observed["belief"]["version"] == 1
    assert observed["lastOutcome"]["instrumentId"] == first
    # Replaying the returned history gives exactly the same belief.
    replay = client.post(
        "/api/science/belief", json={"missionState": state, "history": observed["history"]}
    ).json()["data"]
    assert replay["belief"] == observed["belief"]


def test_hidden_truth_never_in_payload(client: TestClient) -> None:
    state = _default(client)
    model = load_science_models()["neo-rendezvous"]
    truth = hidden_truth(model, state["randomSeed"])
    history: list[dict[str, str]] = []
    for _ in range(4):
        r = client.post(
            "/api/science/belief",
            json={
                "missionState": state,
                "history": history,
                "observeWith": "inst-vnir-spectrometer",
            },
        )
        data = r.json()["data"]
        history = data["history"]
        text = json.dumps(r.json())
        assert "truth" not in text.lower()
        # The truth id appears only where every hypothesis id appears (hypotheses, tables,
        # belief); there is no field that singles it out.
        other = next(h.id for h in model.hypotheses if h.id != truth)
        assert text.count(f'"{truth}"') == text.count(f'"{other}"')
        assert set(data) == {
            "missionId", "designRevision", "modelVersion", "hypotheses", "likelihoods", "belief",
            "history", "lastOutcome", "nextObservations", "disclaimer",
        }  # fmt: skip


def test_invalid_requests(client: TestClient) -> None:
    state = _default(client)
    bad_inst = client.post(
        "/api/science/belief", json={"missionState": state, "observeWith": "inst-magnetometer"}
    )
    assert (
        bad_inst.status_code == 422
        and bad_inst.json()["error"]["details"]["code"] == "INSTRUMENT_NOT_AVAILABLE"
    )
    bad_outcome = client.post(
        "/api/science/belief",
        json={
            "missionState": state,
            "history": [{"instrumentId": "inst-vnir-spectrometer", "outcomeId": "nope"}],
        },
    )
    assert bad_outcome.status_code == 422
    lunar = client.post(
        "/api/science/belief", json={"missionState": _default(client, "lunar-polar-scout")}
    )
    assert lunar.status_code == 404 and lunar.json()["error"]["code"] == "SCIENCE_MODEL_UNAVAILABLE"

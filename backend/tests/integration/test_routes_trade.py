"""POST /api/mission/trade-study (Task 3.5)."""

import json
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_clock
from app.main import create_app

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
TRADE = "/api/mission/trade-study"


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_clock] = lambda: lambda: NOW
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _default(client: TestClient) -> dict[str, Any]:
    state: dict[str, Any] = client.get("/api/templates/neo-rendezvous/default-mission").json()[
        "data"
    ]
    return state


def _alt(state: dict[str, Any], **arch: Any) -> dict[str, Any]:
    out: dict[str, Any] = json.loads(json.dumps(state))
    out["architecture"].update(arch)
    return out


def _trade(client: TestClient, base: dict[str, Any], alts: list[dict[str, Any]]) -> Any:
    return client.post(TRADE, json={"baseMissionState": base, "alternatives": alts})


def test_returns_base_analysis_and_per_alternative_deltas(client: TestClient) -> None:
    base = _default(client)
    r = _trade(client, base, [_alt(base, communicationsId="comms-xband-medium")])
    body = r.json()
    assert r.status_code == 200 and body["ok"] is True
    data = body["data"]
    base_a = data["baseAnalysis"]
    alt_a = data["alternatives"][0]["analysis"]
    assert len(data["alternatives"]) == 1
    deltas = data["alternatives"][0]["deltas"]
    assert deltas["wet_mass_kg"] == pytest.approx(
        alt_a["budgets"]["wetMassKg"]["value"] - base_a["budgets"]["wetMassKg"]["value"]
    )
    assert deltas["total_score"] == pytest.approx(
        alt_a["score"]["total"] - base_a["score"]["total"]
    )
    validated = client.post("/api/mission/validate", json={"missionState": base}).json()
    assert base_a == validated["data"]["analysis"]


def test_three_alternatives_and_base_untouched(client: TestClient) -> None:
    base = _default(client)
    snapshot = json.dumps(base, sort_keys=True)
    alts = [
        _alt(base, communicationsId="comms-xband-medium"),
        _alt(base, communicationsId="comms-xband-medium"),
        _alt(base),
    ]
    r = _trade(client, base, alts)
    assert r.status_code == 200 and len(r.json()["data"]["alternatives"]) == 3
    assert json.dumps(base, sort_keys=True) == snapshot
    assert all(v == 0 for v in r.json()["data"]["alternatives"][2]["deltas"].values())


def test_rejects_zero_and_four_alternatives(client: TestClient) -> None:
    base = _default(client)
    for alts in ([], [base, base, base, base]):
        r = _trade(client, base, alts)
        assert r.status_code == 422
        err = r.json()["error"]
        assert r.json()["ok"] is False and err["code"] == "VALIDATION_ERROR"
        assert any(f["path"].startswith("alternatives") for f in err["details"]["fields"])


def test_unknown_component_names_the_alternative_index(client: TestClient) -> None:
    base = _default(client)
    good = _alt(base, communicationsId="comms-xband-medium")
    bad = _alt(base, communicationsId="comms-nope")
    r = _trade(client, base, [good, bad])
    err = r.json()["error"]
    assert r.status_code == 422 and err["code"] == "CATALOG_ITEM_NOT_FOUND"
    assert err["details"]["design"] == {"role": "alternative", "index": 1}
    assert err["details"]["items"][0]["id"] == "comms-nope"


def test_invalid_base_is_reported_as_base(client: TestClient) -> None:
    base = _default(client)
    r = _trade(client, _alt(base, communicationsId="comms-nope"), [base])
    assert r.status_code == 422
    assert r.json()["error"]["details"]["design"] == {"role": "base", "index": None}


def test_inconsistent_alternative_is_validation_error(client: TestClient) -> None:
    base = _default(client)
    bad = json.loads(json.dumps(base))
    bad["scienceObjectives"].append(bad["scienceObjectives"][0])  # duplicate id
    r = _trade(client, base, [bad])
    err = r.json()["error"]
    assert r.status_code == 422 and err["code"] == "VALIDATION_ERROR"
    assert err["details"]["design"] == {"role": "alternative", "index": 0}
    assert err["details"]["issues"]


def test_three_designs_p95_under_300ms(client: TestClient) -> None:
    base = _default(client)
    alts = [_alt(base, communicationsId="comms-xband-medium") for _ in range(3)]
    assert _trade(client, base, alts).status_code == 200  # warm-up
    samples: list[float] = []
    for _ in range(40):
        t0 = time.perf_counter()
        r = _trade(client, base, alts)
        samples.append(time.perf_counter() - t0)
        assert r.status_code == 200
    samples.sort()
    p95 = samples[int(0.95 * len(samples)) - 1]
    print(f"trade-study (3 alternatives + base) p95 = {p95 * 1000:.1f} ms over {len(samples)} runs")
    assert p95 < 0.300

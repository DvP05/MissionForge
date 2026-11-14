"""Evidence Passport v2 (Task 6.9, AC-22): Phase 6 evidence joined onto a Phase 4 run."""

import json
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_clock
from app.main import create_app
from app.services.research_evidence_service import (
    PASSPORT_PARETO_CANDIDATES,
    PASSPORT_ROBUSTNESS_SAMPLES,
)

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
DOSSIER = "/api/mission/dossier"


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_clock] = lambda: lambda: NOW
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="module")
def run(client: TestClient) -> dict[str, Any]:
    state: dict[str, Any] = client.get("/api/templates/neo-rendezvous/default-mission").json()[
        "data"
    ]
    state["architecture"]["communicationsId"] = "comms-xband-medium"
    r = client.post("/api/mission/simulate", json={"missionState": state, "randomSeed": 42})
    out: dict[str, Any] = r.json()["data"]["run"]
    return out


@pytest.fixture(scope="module")
def exported(client: TestClient, run: dict[str, Any]) -> dict[str, Any]:
    body = client.post(DOSSIER, json={"run": run}).json()
    assert body["ok"] is True, body
    data: dict[str, Any] = body["data"]
    return data


def test_package_carries_research_evidence(exported: dict[str, Any], run: dict[str, Any]) -> None:
    research = exported["package"]["research"]
    seed = run["inputSnapshot"]["randomSeed"]
    # STM / MTM
    assert research["scienceTraceability"] and research["missionTraceability"]
    assert {r["objectiveId"] for r in research["scienceTraceability"]} >= {
        o["id"] for o in run["inputSnapshot"]["scienceObjectives"]
    }
    # Pareto position
    pareto = research["pareto"]
    assert pareto["seed"] == seed
    assert pareto["candidatesEvaluated"] <= PASSPORT_PARETO_CANDIDATES
    assert pareto["frontSize"] >= 1 and set(pareto["archetypes"]) <= {
        "lean",
        "science-max",
        "resilient",
    }
    assert pareto["baselineOnFront"] or pareto["dominatedBy"] or not pareto["baselineFeasible"]
    # Robustness seed / N / assumptions / disclaimer
    rob = research["robustness"]
    assert rob["samples"] == PASSPORT_ROBUSTNESS_SAMPLES and rob["seed"] == seed
    assert rob["assumptions"] and "not a flight-qualified" in rob["disclaimer"]
    # Schedule / data cycles
    sched = research["schedule"]
    assert sched["cycles"] and sched["accepted"]
    # Honest about what is not included; autonomy and health are now part of the passport
    assert any("belief" in n.lower() for n in research["notIncluded"])
    assert not any("autonomy" in n.lower() for n in research["notIncluded"])
    assert isinstance(research["healthFindings"], list)


def test_html_has_v2_sections(exported: dict[str, Any]) -> None:
    html = exported["html"]
    for heading in (
        "Traceability matrices",
        "Science traceability (STM)",
        "Mission traceability (MTM)",
        "Design-space position",
        "Robustness",
        "Science and downlink schedule",
        "Onboard autonomy",
        "Health monitor",
        "Not included",
        # v1 sections that AC-22 also lists
        "Anomalies",
        "Limitations",
    ):
        assert heading in html, heading
    assert "greedy heuristic" in html.lower()
    assert "Wilson 95% interval" in html


def test_research_is_deterministic(client: TestClient, run: dict[str, Any]) -> None:
    a = client.post(DOSSIER, json={"run": run}).json()["data"]
    b = client.post(DOSSIER, json={"run": run}).json()["data"]
    assert a["package"]["research"] == b["package"]["research"]
    assert a["html"] == b["html"]


def test_import_drops_client_research_and_still_replays(
    client: TestClient, exported: dict[str, Any], run: dict[str, Any]
) -> None:
    pkg = json.loads(json.dumps(exported["package"]))
    pkg["research"]["robustness"]["probabilityFeasible"] = 1.0  # forged client claim
    imported = client.post(
        "/api/mission/import", content=json.dumps(pkg), headers={"Content-Type": "application/json"}
    ).json()
    assert imported["ok"] is True, imported
    assert imported["data"]["package"]["research"] is None
    replay = client.post("/api/mission/replay", json={"run": run}).json()["data"]
    assert replay["identical"] is True


def test_v1_package_without_research_still_imports(
    client: TestClient, exported: dict[str, Any]
) -> None:
    pkg = json.loads(json.dumps(exported["package"]))
    del pkg["research"]
    imported = client.post(
        "/api/mission/import", content=json.dumps(pkg), headers={"Content-Type": "application/json"}
    ).json()
    assert imported["ok"] is True, imported


def test_export_stays_fast(client: TestClient, run: dict[str, Any]) -> None:
    start = time.perf_counter()
    client.post(DOSSIER, json={"run": run})
    assert time.perf_counter() - start < 6.0

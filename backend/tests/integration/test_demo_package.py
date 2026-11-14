"""Task 7.5: the shipped demo mission package imports, replays identically and has not drifted."""

import json
import os
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import DEFAULT_DEMO_PACKAGE
from app.main import create_app
from scripts.make_demo_package import build_demo_package

REGEN = "uv run python -m scripts.make_demo_package"


@pytest.fixture(scope="module")
def shipped() -> dict[str, Any]:
    assert DEFAULT_DEMO_PACKAGE.is_file(), f"missing demo package; run {REGEN}"
    data: dict[str, Any] = json.loads(DEFAULT_DEMO_PACKAGE.read_text(encoding="utf-8"))
    return data


def test_demo_route_serves_the_shipped_package(shipped: dict[str, Any]) -> None:
    with TestClient(create_app()) as c:
        body = c.get("/api/demo/package").json()
    assert body["ok"] is True
    assert body["data"]["mission"] == shipped["mission"]
    assert body["data"]["runs"][0]["runId"] == shipped["runs"][0]["runId"]


def test_demo_package_imports_and_replays_identically(shipped: dict[str, Any]) -> None:
    with TestClient(create_app()) as c:
        imported = c.post(
            "/api/mission/import",
            content=json.dumps(shipped),
            headers={"Content-Type": "application/json"},
        ).json()
        assert imported["ok"] is True, imported
        replay = c.post("/api/mission/replay", json={"run": shipped["runs"][0]}).json()["data"]
    assert replay["identical"] is True
    run = shipped["runs"][0]
    assert run["finalReport"]["outcome"] in ("success", "partial")
    assert {d["decisionMaker"] for d in run["decisions"]} == {"player"}


def test_demo_package_has_not_drifted(shipped: dict[str, Any]) -> None:
    if os.environ.get("CI") and os.environ.get("UPDATE_GOLDEN") == "1":
        pytest.fail("regenerate the demo package locally, not in CI")
    fresh = build_demo_package()
    assert fresh == shipped, f"demo package drifted from the engine; run {REGEN} and review"

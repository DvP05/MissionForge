"""Build the seeded demo mission package (Task 7.5) -> data/demo/demo-saved.json.

The demo snapshot keeps the judging demo independent of any network: the NEO starter with
the medium radio (mission-ready), seed 42, both scenario decisions made by the player,
exported through the real passport route with a fixed clock so the file is reproducible.
``tests/integration/test_demo_package.py`` fails if the committed file drifts.

Run: uv run python -m scripts.make_demo_package
"""

import json
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from app.api.deps import get_clock, get_mission_id_factory
from app.config import DEFAULT_DEMO_PACKAGE
from app.main import create_app

DEMO_NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
DEMO_MISSION_ID = "mission-demo00000001"
DEMO_SEED = 42
DEMO_DECISIONS = (
    ("scenario-target-illumination", "extend-observation"),
    ("scenario-solar-event", "pause-science"),
)


def build_demo_package() -> dict[str, Any]:
    app = create_app()
    app.dependency_overrides[get_clock] = lambda: lambda: DEMO_NOW
    app.dependency_overrides[get_mission_id_factory] = lambda: lambda: DEMO_MISSION_ID
    with TestClient(app) as c:
        state: dict[str, Any] = c.get("/api/templates/neo-rendezvous/default-mission").json()[
            "data"
        ]
        state["missionId"] = DEMO_MISSION_ID
        state["title"] = "Echoes of Origins (saved demo)"
        state["architecture"]["communicationsId"] = "comms-xband-medium"
        state["designRevision"] = 1
        sim = c.post("/api/mission/simulate", json={"missionState": state, "randomSeed": DEMO_SEED})
        run: dict[str, Any] = sim.json()["data"]["run"]
        for event_id, choice_id in DEMO_DECISIONS:
            r = c.post(
                f"/api/mission/run/{run['runId']}/decision",
                json={"eventId": event_id, "choiceId": choice_id},
            ).json()
            assert r["ok"], r
            run = r["data"]["run"]
        body = c.post("/api/mission/dossier", json={"run": run}).json()
        assert body["ok"] and body["data"]["replayStatus"] == "identical-replay", body
        package: dict[str, Any] = body["data"]["package"]
        return package


def main() -> None:
    package = build_demo_package()
    text = json.dumps(package, indent=2, sort_keys=True) + "\n"
    DEFAULT_DEMO_PACKAGE.write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {DEFAULT_DEMO_PACKAGE}")


if __name__ == "__main__":
    main()

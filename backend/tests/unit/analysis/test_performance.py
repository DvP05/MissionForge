"""analyze_mission performance budget: p95 < 100 ms (global constraint; Task 2.8 (f))."""

import time
from datetime import UTC, datetime

from app.config import DEFAULT_CATALOG_DIR, DEFAULT_MISSIONS_DIR
from app.domain.analysis.orchestrator import (
    ENGINE_VERSION,
    analyze_mission,
    scenario_inputs_from_template,
)
from app.domain.catalog.loader import load_catalog
from app.domain.mission.defaults import default_mission_state, list_templates

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
RUNS = 200
P95_BUDGET_S = 0.100


def test_analyze_mission_p95_under_100ms() -> None:
    catalog = load_catalog(DEFAULT_CATALOG_DIR)  # loaded once, outside the timed loop
    template = next(
        t for t in list_templates(DEFAULT_MISSIONS_DIR) if t.scenario_id == "neo-rendezvous"
    )
    scenario = scenario_inputs_from_template(template)
    state = default_mission_state(
        "neo-rendezvous", mission_id="perf", seed=1, now=NOW, templates_dir=DEFAULT_MISSIONS_DIR
    )
    analyze_mission(state, catalog, scenario=scenario, engine_version=ENGINE_VERSION, now=NOW)
    samples: list[float] = []
    for _ in range(RUNS):
        t0 = time.perf_counter()
        analyze_mission(state, catalog, scenario=scenario, engine_version=ENGINE_VERSION, now=NOW)
        samples.append(time.perf_counter() - t0)
    samples.sort()
    p95 = samples[int(0.95 * RUNS) - 1]
    print(f"analyze_mission p95 = {p95 * 1000:.2f} ms over {RUNS} runs")
    assert p95 < P95_BUDGET_S, f"p95 {p95 * 1000:.1f} ms exceeds 100 ms"

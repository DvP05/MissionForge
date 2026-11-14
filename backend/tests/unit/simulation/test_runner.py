"""run_mission: nominal deterministic run, golden, launch gate, events, telemetry (Task 4.1)."""

import json
import math
import os
import time
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.config import DEFAULT_SCENARIOS_DIR
from app.domain.catalog.loader import Catalog
from app.domain.errors import DomainValidationError
from app.domain.simulation.anomalies import load_event_sets
from app.domain.simulation.runner import LaunchBlocked, run_mission
from app.domain.simulation.telemetry import TELEMETRY_CHANNELS, TELEMETRY_UNITS
from app.schemas.mission import MissionState
from app.schemas.simulation import MissionRun, SimulationInput
from tests.unit.simulation.conftest import APP_VERSION, MEDIUM, SimFactory, make_state

GOLDEN = Path(__file__).resolve().parents[2] / "golden" / "neo_run_seed42.json"
REGEN_HINT = "UPDATE_GOLDEN=1 uv run python -m pytest tests/unit/simulation/test_runner.py"
SCENARIO_VERSION = "0.1.0"
EVENT_SETS = load_event_sets(DEFAULT_SCENARIOS_DIR)


def _run(
    sim_input_for: SimFactory,
    catalog: Catalog,
    state: MissionState | None = None,
    *,
    experimental: bool = False,
    seed: int | None = None,
    decisions: dict[str, str] | None = None,
) -> MissionRun:
    sim, scenario = sim_input_for(
        state or make_state(communications_id=MEDIUM), experimental=experimental, seed=seed
    )
    return run_mission(
        sim,
        catalog,
        event_sets=EVENT_SETS,
        scenario=scenario,
        decisions=decisions,
        scenario_version=SCENARIO_VERSION,
        app_version=APP_VERSION,
    )


def _approx_equal(a: Any, b: Any, path: str = "$") -> None:
    """Exact structure; floats equal within 1e-9 relative (libm may differ by an ulp)."""
    if isinstance(a, float) or isinstance(b, float):
        assert isinstance(a, int | float) and isinstance(b, int | float), path
        assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12), f"{path}: {a} != {b}"
    elif isinstance(a, dict):
        assert isinstance(b, dict) and list(a) == list(b), f"{path}: keys differ"
        for k in a:
            _approx_equal(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), f"{path}: length differs"
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            _approx_equal(x, y, f"{path}[{i}]")
    else:
        assert a == b, f"{path}: {a!r} != {b!r}"


# --- reproducibility (AC-11) -----------------------------------------------------------


def test_same_input_twice_is_byte_identical(sim_input_for: SimFactory, catalog: Catalog) -> None:
    a = _run(sim_input_for, catalog)
    b = _run(sim_input_for, catalog)
    assert a.model_dump_json() == b.model_dump_json()
    assert a.run_id == b.run_id


def test_run_matches_golden(sim_input_for: SimFactory, catalog: Catalog) -> None:
    payload = _run(sim_input_for, catalog).model_dump(mode="json", by_alias=True)
    if os.environ.get("UPDATE_GOLDEN") == "1":
        if os.environ.get("CI"):
            pytest.fail("UPDATE_GOLDEN is not allowed in CI; golden files must be committed")
        GOLDEN.parent.mkdir(exist_ok=True)
        text = json.dumps(payload, indent=2, sort_keys=False) + "\n"
        GOLDEN.write_text(text, encoding="utf-8", newline="\n")
    assert GOLDEN.exists(), f"missing golden {GOLDEN.name}; run: {REGEN_HINT}"
    _approx_equal(payload, json.loads(GOLDEN.read_text(encoding="utf-8")))


def test_golden_regen_refused_in_ci(
    monkeypatch: pytest.MonkeyPatch, sim_input_for: SimFactory, catalog: Catalog
) -> None:
    monkeypatch.setenv("UPDATE_GOLDEN", "1")
    monkeypatch.setenv("CI", "true")
    with pytest.raises(pytest.fail.Exception, match="not allowed in CI"):
        test_run_matches_golden(sim_input_for, catalog)


def test_run_id_depends_on_seed_and_is_stable(sim_input_for: SimFactory, catalog: Catalog) -> None:
    a = _run(sim_input_for, catalog)
    b = _run(sim_input_for, catalog, seed=43)
    assert a.run_id.startswith("run-") and a.run_id != b.run_id
    assert b.seed == 43 and b.manifest.seed == 43


def test_simulation_under_one_second(sim_input_for: SimFactory, catalog: Catalog) -> None:
    sim, scenario = sim_input_for(make_state(communications_id=MEDIUM))
    t0 = time.perf_counter()
    run_mission(
        sim, catalog, scenario=scenario, event_sets=EVENT_SETS, scenario_version=SCENARIO_VERSION,
        app_version=APP_VERSION,
    )  # fmt: skip
    assert time.perf_counter() - t0 < 1.0


# --- identity, snapshot, manifest, immutability ---------------------------------------


def test_run_records_design_revision_snapshot_and_manifest(
    sim_input_for: SimFactory, catalog: Catalog
) -> None:
    state = make_state(communications_id=MEDIUM)
    run = _run(sim_input_for, catalog, state)
    assert run.design_revision == state.design_revision
    assert run.mission_id == state.mission_id
    assert run.input_snapshot == state
    assert run.experimental is False
    m = run.manifest
    assert (m.schema_version, m.engine_version, m.catalog_version) == ("1.0", "0.1.0", "0.1.0")
    assert (m.scenario_version, m.app_version, m.seed) == ("0.1.0", "0.1.0", 42)
    assert m.event_set_id == run.scenario_event_set_id == "neo-rendezvous-nominal-v1"
    assert run.decisions == () and run.autonomy_log == ()


def test_run_is_immutable(sim_input_for: SimFactory, catalog: Catalog) -> None:
    run = _run(sim_input_for, catalog)
    with pytest.raises(ValidationError):
        run.seed = 1  # type: ignore[misc]
    hash(run)


# --- launch gate ------------------------------------------------------------------------


def test_infeasible_design_is_launch_blocked(sim_input_for: SimFactory, catalog: Catalog) -> None:
    state = make_state()  # lowgain starter: link-margin fails
    with pytest.raises(LaunchBlocked) as exc:
        _run(sim_input_for, catalog, state)
    assert isinstance(exc.value, DomainValidationError)
    assert exc.value.code == "LAUNCH_BLOCKED"
    assert "link-margin" in exc.value.failing_constraint_ids
    assert "link-margin" in exc.value.message


def test_infeasible_design_runs_when_experimental(
    sim_input_for: SimFactory, catalog: Catalog
) -> None:
    run = _run(sim_input_for, catalog, make_state(), experimental=True)
    assert run.experimental is True
    assert run.final_report.outcome == "failure"  # nothing is returned over the failed link
    assert all(o.returned_fraction == 0.0 for o in run.science_outcomes)
    assert all(o.collected_fraction > 0.0 for o in run.science_outcomes)
    lost = [e for e in run.events if e.type == "downlink"]
    assert lost and all(e.severity == "warning" for e in lost)
    assert all(e.trigger.get("ref") == "architecture.communicationsId" for e in lost)


def test_analysis_for_another_revision_is_rejected(
    sim_input_for: SimFactory, catalog: Catalog
) -> None:
    sim, scenario = sim_input_for(make_state(communications_id=MEDIUM))
    dump = sim.mission_state.model_dump()
    stale = SimulationInput.model_validate(
        {**sim.model_dump(), "mission_state": {**dump, "design_revision": 1}}
    )
    with pytest.raises(DomainValidationError) as exc:
        run_mission(
            stale,
            catalog,
            scenario=scenario,
            event_sets=EVENT_SETS,
            scenario_version="0.1.0",
            app_version="0.1.0",
        )
    assert exc.value.code == "ANALYSIS_REVISION_MISMATCH"


def test_unknown_decision_event_is_rejected(sim_input_for: SimFactory, catalog: Catalog) -> None:
    with pytest.raises(DomainValidationError) as exc:
        _run(sim_input_for, catalog, decisions={"no-such-event": "a"})
    assert exc.value.code == "UNKNOWN_DECISION_EVENT"


# --- phases and events ----------------------------------------------------------------


def test_six_plus_phases_in_order(sim_input_for: SimFactory, catalog: Catalog) -> None:
    run = _run(sim_input_for, catalog)
    assert run.phases == (
        "launch-deployment", "commissioning", "cruise", "mid-course", "approach",
        "science-ops", "downlink-return", "complete",
    )  # fmt: skip
    assert [t.phase for t in run.phase_transitions] == list(run.phases)
    assert len(set(run.phases)) >= 6


def test_every_event_is_explained_and_traceable(
    sim_input_for: SimFactory, catalog: Catalog
) -> None:
    run = _run(sim_input_for, catalog)
    ids = [e.id for e in run.events]
    assert len(ids) == len(set(ids))
    for e in run.events:
        assert e.id == f"{e.phase}-{e.type}-{e.id.rsplit('-', 1)[1]}"
        assert e.severity in ("info", "warning", "critical")
        assert e.title and len(e.description) > 20
        assert e.trigger.get("source") in ("design", "scenario-event"), e.id
        ref = e.trigger.get("ref")
        assert isinstance(ref, str) and ref, e.id
        assert e.decision_maker == "system"
    types = {e.type for e in run.events}
    assert {"milestone", "science", "downlink"} <= types
    milestones = [e for e in run.events if e.type == "milestone"]
    assert {e.phase for e in milestones} >= set(run.phases)


def test_event_ids_are_stable_across_runs(sim_input_for: SimFactory, catalog: Catalog) -> None:
    a = _run(sim_input_for, catalog)
    b = _run(sim_input_for, catalog, seed=7)
    assert [e.id for e in a.events] == [e.id for e in b.events]
    assert a.events[0].id == "launch-deployment-milestone-1"


def test_events_sorted_with_sequence_tie_break(sim_input_for: SimFactory, catalog: Catalog) -> None:
    run = _run(sim_input_for, catalog)
    assert [e.sequence for e in run.events] == list(range(len(run.events)))
    keys = [(e.mission_day, e.sequence) for e in run.events]
    assert keys == sorted(keys)
    by_day: dict[float, list[int]] = {}
    for e in run.events:
        by_day.setdefault(e.mission_day, []).append(e.sequence)
    ties = {d: s for d, s in by_day.items() if len(s) > 1}
    assert ties, "the NEO plan has same-day events (day 300 observation + contact)"
    for seqs in ties.values():
        assert seqs == sorted(seqs)
    day300 = [e for e in run.events if e.mission_day == 300.0]
    assert [e.type for e in day300] == ["science", "downlink"]


def test_rendezvous_burn_event_references_trajectory(
    sim_input_for: SimFactory, catalog: Catalog
) -> None:
    run = _run(sim_input_for, catalog)
    burn = next(e for e in run.events if e.trigger.get("ref") == "trajectory.missionDeltaVKmPerS")
    assert burn.mission_day == 275.0 and burn.phase == "approach"


# --- telemetry -----------------------------------------------------------------------


def test_telemetry_channels_and_units(sim_input_for: SimFactory, catalog: Catalog) -> None:
    run = _run(sim_input_for, catalog)
    assert set(TELEMETRY_CHANNELS) == {
        "battery_soc", "propellant_fraction", "buffer_fill", "link_margin_db",
        "pointing_error_deg",
    }  # fmt: skip
    for s in run.telemetry:
        assert s.channel in TELEMETRY_CHANNELS
        assert s.unit == TELEMETRY_UNITS[s.channel]
        assert s.fidelity in ("derived", "gameplay-estimate")
        if s.unit == "fraction":
            assert 0.0 <= s.value <= 1.0
    for t in run.phase_transitions:
        chans = {
            s.channel for s in run.telemetry
            if s.mission_day == t.mission_day and s.phase == t.phase
        }  # fmt: skip
        assert len(chans) >= 3, t.phase


def test_telemetry_follows_modeled_state(sim_input_for: SimFactory, catalog: Catalog) -> None:
    run = _run(sim_input_for, catalog)

    def series(ch: str) -> list[tuple[float, float]]:
        return [(s.mission_day, s.value) for s in run.telemetry if s.channel == ch]

    prop = series("propellant_fraction")
    assert prop[0][1] == 1.0 and prop[-1][1] < 1.0  # the rendezvous burn used propellant
    assert all(b[1] <= a[1] for a, b in zip(prop, prop[1:], strict=False))
    assert all(v == 1.0 for d, v in prop if d < 275.0)
    links = series("link_margin_db")
    assert len(links) == len(run.input_snapshot.operations.downlink_plan)
    assert all(v == pytest.approx(6.71, abs=0.05) for _, v in links)
    buffer = series("buffer_fill")
    assert buffer[0][1] == 0.0 and max(v for _, v in buffer) > 0.0
    days = [s.mission_day for s in run.telemetry]
    assert days == sorted(days)


def test_telemetry_does_not_overclaim_fidelity(sim_input_for: SimFactory, catalog: Catalog) -> None:
    run = _run(sim_input_for, catalog)
    pointing = {s.fidelity for s in run.telemetry if s.channel == "pointing_error_deg"}
    assert pointing == {"gameplay-estimate"}
    assert all(s.fidelity != "source-backed" for s in run.telemetry)


# --- science and report ---------------------------------------------------------------


def test_science_outcomes_and_report(sim_input_for: SimFactory, catalog: Catalog) -> None:
    state = make_state(communications_id=MEDIUM)
    sim, _ = sim_input_for(state)
    run = _run(sim_input_for, catalog, state)
    assert [o.objective_id for o in run.science_outcomes] == [
        o.id for o in state.science_objectives
    ]
    cov = sim.analysis.science.weighted_objective_coverage
    for o in run.science_outcomes:
        assert o.returned_fraction == pytest.approx(cov[o.objective_id])
        assert o.collected_fraction >= o.returned_fraction
    report = run.final_report
    assert report.score == sim.analysis.score
    assert report.outcome == "success"
    assert any("not orbital propagation" in x for x in report.limitations)
    assert report.summary


@pytest.mark.parametrize("scenario", ["neo-rendezvous", "lunar-polar-scout", "earth-observation"])
def test_every_starter_runs_experimentally(
    scenario: str, sim_input_for: SimFactory, catalog: Catalog
) -> None:
    run = _run(sim_input_for, catalog, make_state(scenario), experimental=True)
    assert run.phases[-1] == "complete"
    json.loads(run.model_dump_json())  # finite, serialisable


def test_empty_plans_run_without_nan(sim_input_for: SimFactory, catalog: Catalog) -> None:
    dump = make_state(communications_id=MEDIUM).model_dump()
    dump["operations"] = {**dump["operations"], "observation_plan": [], "downlink_plan": []}
    state = MissionState.model_validate(dump)
    run = _run(sim_input_for, catalog, state, experimental=True)
    assert not [e for e in run.events if e.type in ("science", "downlink")]
    assert all(o.status == "missed" for o in run.science_outcomes)
    assert run.final_report.outcome == "failure"
    assert "NaN" not in run.model_dump_json()


# --- fix round 1: schedule wording, missing science, extended end, single-source limits ---


def test_leo_run_uses_orbit_wording(sim_input_for: SimFactory, catalog: Catalog) -> None:
    run = _run(sim_input_for, catalog, make_state("earth-observation"), experimental=True)
    entered = {t.phase for t in run.phase_transitions}
    assert entered == set(run.phases) and len(run.phases) == 8
    text = " ".join(f"{e.title} {e.description}" for e in run.events).lower()
    assert "rendezvous" not in text and "transfer toward" not in text
    burn = next(e for e in run.events if e.trigger.get("ref") == "trajectory.missionDeltaVKmPerS")
    assert burn.title == "Primary maneuver"


def test_lunar_run_arrives_on_time_of_flight(sim_input_for: SimFactory, catalog: Catalog) -> None:
    run = _run(sim_input_for, catalog, make_state("lunar-polar-scout"), experimental=True)
    burn = next(e for e in run.events if e.trigger.get("ref") == "trajectory.missionDeltaVKmPerS")
    assert burn.mission_day == 5.0 and burn.title == "Arrival maneuver"
    cruise = next(e for e in run.events if e.id == "cruise-milestone-1")
    assert "arrival on day 5." in cruise.description


def test_observation_never_claims_storage_for_missing_science(
    sim_input_for: SimFactory, catalog: Catalog
) -> None:
    sim, _ = sim_input_for(make_state(), experimental=True)
    missing = set(sim.analysis.science.missing_requirements)
    run = _run(sim_input_for, catalog, make_state(), experimental=True)
    flagged = [
        e for e in run.events if e.type == "science" and e.trigger["measurement_id"] in missing
    ]
    assert flagged
    for e in flagged:
        assert e.severity == "warning"
        assert "data is stored" not in e.description
        assert e.trigger["ref"] == "architecture.communicationsId"


def test_complete_text_uses_extended_end_day(sim_input_for: SimFactory, catalog: Catalog) -> None:
    dump = make_state(communications_id=MEDIUM).model_dump()
    dump["operations"] = {**dump["operations"], "mission_duration_days": 400.0}
    run = _run(sim_input_for, catalog, MissionState.model_validate(dump), experimental=True)
    done = next(e for e in run.events if e.phase == "complete")
    assert done.mission_day == pytest.approx(408.0 + 8.0 / 24.0)
    assert "ends on day 408.333" in done.description and "planned 400 d" in done.description


def test_limitations_reuse_assumption_constants(
    sim_input_for: SimFactory, catalog: Catalog
) -> None:
    from app.domain.simulation.phases import PHASE_ASSUMPTIONS
    from app.domain.simulation.telemetry import TELEMETRY_ASSUMPTIONS

    limits = _run(sim_input_for, catalog).final_report.limitations
    assert set(PHASE_ASSUMPTIONS) <= set(limits) and set(TELEMETRY_ASSUMPTIONS) <= set(limits)
    assert len(limits) == len(set(limits))

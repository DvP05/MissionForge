"""Blackout autonomy inside run_mission (Task 6.5, AC-19, Phase 4 <-> 6 join)."""

from typing import Any

from app.config import DEFAULT_SCENARIOS_DIR
from app.domain.catalog.loader import Catalog
from app.domain.simulation.anomalies import load_event_sets
from app.domain.simulation.runner import run_mission
from app.schemas.mission import MissionState
from app.schemas.simulation import MissionRun
from app.services.science_service import load_science_models
from tests.unit.simulation.conftest import APP_VERSION, MEDIUM, SimFactory, make_state

EVENT_SETS = load_event_sets(DEFAULT_SCENARIOS_DIR)
MODELS = load_science_models()


def _state(safe_mode: str = "balanced", **ops: Any) -> MissionState:
    s = make_state(communications_id=MEDIUM)
    dump = s.model_dump()
    dump["operations"] = {**dump["operations"], "safe_mode_policy": safe_mode, **ops}
    return MissionState.model_validate(dump)


def _run(sim_input_for: SimFactory, catalog: Catalog, state: MissionState) -> MissionRun:
    sim, scenario = sim_input_for(state)
    return run_mission(
        sim, catalog, event_sets=EVENT_SETS, scenario=scenario, scenario_version="0.1.0",
        app_version=APP_VERSION, science_model=MODELS.get(state.scenario_id),
    )  # fmt: skip


def test_authority_follows_planned_contacts(sim_input_for: SimFactory, catalog: Catalog) -> None:
    run = _run(sim_input_for, catalog, _state())
    makers = [d.decision_maker for d in run.autonomy_log]
    # NEO plan: day 300 falls inside the day-300 pass; days 290 / 310 / 320 are blackouts.
    assert makers == ["onboard-policy", "ground", "onboard-policy", "onboard-policy"]
    for d in run.autonomy_log:
        assert d.policy == "resource-aware" and d.reason and d.candidates


def test_belief_updates_from_observations_without_leaking_truth(
    sim_input_for: SimFactory, catalog: Catalog
) -> None:
    run = _run(sim_input_for, catalog, _state())
    first, last = run.autonomy_log[0].belief, run.autonomy_log[-1].belief
    assert len(first.hypotheses) == 3 and first.version == 0
    assert last.version > first.version  # earlier observations updated the belief
    assert abs(sum(h.probability for h in last.hypotheses) - 1.0) < 1e-9
    assert "truth" not in run.model_dump_json().lower()


def test_conservative_hold_removes_the_observation_and_its_science(
    sim_input_for: SimFactory, catalog: Catalog
) -> None:
    nominal = _run(sim_input_for, catalog, _state("balanced"))
    cons = _run(sim_input_for, catalog, _state("conservative"))
    held = [d for d in cons.autonomy_log if d.selected_action_id is None]
    assert held, "conservative should hold a low-information blackout observation"
    assert all(d.decision_maker == "onboard-policy" for d in held)
    assert any(
        e.title.startswith("Observation held onboard") and e.decision_maker == "onboard-policy"
        for e in cons.events
    )
    collected = lambda r: sum(o.collected_fraction for o in r.science_outcomes)  # noqa: E731
    assert collected(cons) < collected(nominal)


def test_same_input_same_autonomy_log(sim_input_for: SimFactory, catalog: Catalog) -> None:
    s = _state("aggressive")
    assert (
        _run(sim_input_for, catalog, s).autonomy_log == _run(sim_input_for, catalog, s).autonomy_log
    )


def test_scenario_without_hypothesis_model_logs_empty_belief(
    sim_input_for: SimFactory, catalog: Catalog
) -> None:
    run = _run(sim_input_for, catalog, make_state("lunar-polar-scout"))
    assert run.autonomy_log
    assert all(d.belief.hypotheses == () for d in run.autonomy_log)

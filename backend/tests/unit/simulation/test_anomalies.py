"""Scenario event sets and design-traced anomalies (Task 4.2, architecture 9.4, AC-10)."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from app.config import DEFAULT_SCENARIOS_DIR
from app.domain.errors import DomainValidationError
from app.domain.simulation.anomalies import (
    EFFECT_KEYS,
    ScenarioEventSet,
    default_event_set_id,
    load_event_sets,
    resolve_event_set,
)
from app.schemas.mission import MissionState
from app.schemas.simulation import MissionEvent, MissionRun
from tests.unit.simulation.conftest import (
    EVENT_SET,
    GENERIC_EVENTS,
    MEDIUM,
    NEO_EVENTS,
    RunFactory,
    low_margin_state,
    make_state,
    thin_downlink_state,
)

SOLAR = "scenario-solar-event"
ILLUMINATION = "scenario-target-illumination"
MISSED = "anomaly-missed-contact"
DESIGN_IDS = ("missed-contact", "power-low", "pointing-drift", "correction-shortfall")
DEFAULT_SETS = {
    "neo-rendezvous": NEO_EVENTS,
    "lunar-polar-scout": "lunar-default-v1",
    "earth-observation": "eo-default-v1",
}


def _ev(run: MissionRun, event_id: str) -> MissionEvent:
    found = [e for e in run.events if e.id == event_id]
    assert found, f"no event {event_id}: {[e.id for e in run.events if e.choices]}"
    return found[0]


def _design_anomalies(run: MissionRun) -> list[MissionEvent]:
    return [e for e in run.events if e.id.startswith("anomaly-")]


def _starter_run(run_sim: RunFactory, scenario: str) -> MissionRun:
    return run_sim(make_state(scenario), event_set=DEFAULT_SETS[scenario], experimental=True)


# --- event-set files ---------------------------------------------------------------------


def test_repo_event_sets_load(event_sets: Mapping[str, ScenarioEventSet]) -> None:
    assert {NEO_EVENTS, GENERIC_EVENTS, EVENT_SET, *DEFAULT_SETS.values()} <= set(event_sets)
    neo = event_sets[NEO_EVENTS]
    assert neo.scenario_ids == ("neo-rendezvous",)
    assert [a.id for a in neo.anomalies] == list(DESIGN_IDS)
    assert [s.id for s in neo.scenario_events] == ["solar-event", "target-illumination"]
    assert {s.window for s in neo.scenario_events} == {"science-ops", "approach"}
    for sid in DEFAULT_SETS.values():
        assert len(event_sets[sid].scenario_events) >= 2
        assert [a.id for a in event_sets[sid].anomalies] == list(DESIGN_IDS)
    assert event_sets[EVENT_SET].nominal and EVENT_SET == "nominal-v1"
    assert not event_sets[GENERIC_EVENTS].scenario_events  # design rules only


def test_default_event_set_per_scenario(event_sets: Mapping[str, ScenarioEventSet]) -> None:
    for scenario, sid in DEFAULT_SETS.items():
        assert default_event_set_id(scenario, event_sets) == sid
    with pytest.raises(DomainValidationError) as exc:
        default_event_set_id("mars-sample-return", event_sets)
    assert exc.value.code == "NO_DEFAULT_EVENT_SET"


def test_event_files_are_named_per_scenario() -> None:
    for scenario, sid in DEFAULT_SETS.items():
        raw = json.loads((DEFAULT_SCENARIOS_DIR / f"{scenario}.events.json").read_text("utf-8"))
        assert raw["eventSetId"] == sid and raw["default"] is True


def test_every_declared_effect_uses_the_vocabulary(
    event_sets: Mapping[str, ScenarioEventSet],
) -> None:
    for es in event_sets.values():
        for decl in (*es.anomalies, *es.scenario_events):
            assert set(decl.effects) <= set(EFFECT_KEYS)
            for c in decl.choices:
                assert set(c.effects) <= set(EFFECT_KEYS)
            if decl.choices:
                assert 2 <= len(decl.choices) <= 3
                assert "terminate" not in decl.choices[0].effects  # default keeps the journey
                effects = [tuple(sorted(c.effects.items())) for c in decl.choices]
                assert len(set(effects)) == len(effects), f"{decl.id}: choices not distinct"


def _write_set(tmp_path: Path, **override: Any) -> Path:
    base: dict[str, Any] = {
        "eventSetId": "t-v1",
        "version": "0.1.0",
        "title": "test",
        "scenarioIds": [],
        "assumptions": [],
        "anomalies": [],
        "scenarioEvents": [],
    }
    base.update(override)
    (tmp_path / "t.events.json").write_text(json.dumps(base), encoding="utf-8")
    return tmp_path


def _anomaly(effects: dict[str, float]) -> dict[str, Any]:
    return {
        "id": "x",
        "title": "X",
        "severity": "warning",
        "rule": {"kind": "data-return-shortfall", "severityThreshold": 3.0, "unit": "dB"},
        "situation": "s",
        "counterfactual": "c",
        "effects": effects,
    }


def test_unknown_effect_key_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(DomainValidationError) as exc:
        load_event_sets(_write_set(tmp_path, anomalies=[_anomaly({"science_bonus": 1.0})]))
    assert exc.value.code == "EVENT_SET_INVALID"


def test_out_of_range_effect_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(DomainValidationError) as exc:
        load_event_sets(_write_set(tmp_path, anomalies=[_anomaly({"buffer_loss_fraction": 2.0})]))
    assert exc.value.code == "EVENT_SET_INVALID"


def test_default_set_must_name_scenarios(tmp_path: Path) -> None:
    with pytest.raises(DomainValidationError) as exc:
        load_event_sets(_write_set(tmp_path, default=True))
    assert exc.value.code == "EVENT_SET_INVALID"


def test_resolve_unknown_or_foreign_event_set(event_sets: Mapping[str, ScenarioEventSet]) -> None:
    with pytest.raises(DomainValidationError) as exc:
        resolve_event_set(event_sets, "no-such-set", "neo-rendezvous")
    assert exc.value.code == "UNKNOWN_EVENT_SET"
    with pytest.raises(DomainValidationError) as exc:
        resolve_event_set(event_sets, NEO_EVENTS, "lunar-polar-scout")
    assert exc.value.code == "EVENT_SET_SCENARIO_MISMATCH"
    assert resolve_event_set(event_sets, GENERIC_EVENTS, "lunar-polar-scout").id == GENERIC_EVENTS


def test_run_with_unknown_event_set_is_rejected(run_sim: RunFactory) -> None:
    with pytest.raises(DomainValidationError) as exc:
        run_sim(make_state(communications_id=MEDIUM), event_set="no-such-set")
    assert exc.value.code == "UNKNOWN_EVENT_SET"


# --- design-traced anomalies follow the analysis (R31) ------------------------------------


def test_low_margin_comms_triggers_missed_contact_backlog(run_sim: RunFactory) -> None:
    # the NEO starter's low-gain radio: link-margin fails, data return warns
    starter = run_sim(make_state(), experimental=True)
    ev = _ev(starter, MISSED)
    assert ev.type == "anomaly" and ev.severity == "critical"  # a gating constraint fails
    assert ev.trigger["source"] == "design" and ev.trigger["ref"] == "architecture.communicationsId"
    assert ev.trigger["rule"] == "data-return-shortfall"
    assert ev.trigger["constraint_link-margin"] == "fail"
    assert ev.trigger["constraint_data-return"] == "warning"
    # a feasible-radio design whose contact plan has no slack (data return warns)
    state = thin_downlink_state()
    run = run_sim(state)
    ev = _ev(run, MISSED)
    assert ev.severity == "warning"
    assert ev.trigger["constraint_data-return"] == "warning"
    assert "constraint_link-margin" not in ev.trigger
    assert ev.trigger["plan_item"] == "operations.downlinkPlan[0]"
    assert ev.mission_day == state.operations.downlink_plan[0].start_day
    assert "data backlog" in ev.description and "Why this happened" in ev.description
    assert "analysis flags the downlink" in ev.description
    assert len(ev.choices) >= 2
    missed = [e for e in run.events if e.title.startswith("Ground contact 1 missed")]
    assert missed and missed[0].trigger["caused_by"] == MISSED
    nominal = run_sim(state, event_set=EVENT_SET)

    def peak(r: MissionRun) -> float:
        return max(t.value for t in r.telemetry if t.channel == "buffer_fill")

    assert peak(run) > peak(nominal)
    assert any(r.startswith("missed-contact ") for r in run.final_report.realized_risks)


@pytest.mark.parametrize(
    ("state", "experimental"),
    [
        (make_state(communications_id=MEDIUM), False),
        (low_margin_state(), False),  # 3.7 dB but every analysis check passes
        (make_state(communications_id="comms-xband-highgain"), True),  # budget fail only
        (make_state(communications_id=MEDIUM, power_id="power-xl"), True),
    ],
)
def test_ample_margin_design_has_no_design_anomalies(
    run_sim: RunFactory, state: MissionState, experimental: bool
) -> None:
    run = run_sim(state, experimental=experimental)
    assert _design_anomalies(run) == []
    choice_events = [e for e in run.events if e.choices]
    assert len(choice_events) >= 2  # AC-10 still holds without any design weakness
    assert {e.id for e in choice_events} == {SOLAR, ILLUMINATION}
    assert all(e.trigger["source"] == "scenario-event" for e in choice_events)
    assert not any(r.startswith(DESIGN_IDS) for r in run.final_report.realized_risks)


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("neo-rendezvous", {MISSED}),  # lowgain starter: link-margin fail
        ("lunar-polar-scout", {MISSED}),  # data-return warning only
        ("earth-observation", {MISSED}),  # data-return warning only
    ],
)
def test_starter_anomaly_set_is_pinned(
    run_sim: RunFactory, scenario: str, expected: set[str]
) -> None:
    run = _starter_run(run_sim, scenario)
    assert {e.id for e in _design_anomalies(run)} == expected


def test_neo_medium_starter_has_no_design_anomaly(run_sim: RunFactory) -> None:
    assert _design_anomalies(run_sim(make_state(communications_id=MEDIUM))) == []


@pytest.mark.parametrize("scenario", list(DEFAULT_SETS))
def test_every_starter_offers_two_decisions(run_sim: RunFactory, scenario: str) -> None:
    run = _starter_run(run_sim, scenario)
    decisions = [e for e in run.events if e.choices]
    assert len([e for e in decisions if e.id.startswith("scenario-")]) >= 2  # AC-10
    for e in decisions:
        assert 2 <= len(e.choices) <= 3
        assert len({tuple(sorted(c.effects.items())) for c in e.choices}) == len(e.choices)
        assert all(c.tradeoff for c in e.choices)


def test_low_battery_reserve_triggers_power_low(run_sim: RunFactory) -> None:
    state = make_state(communications_id=MEDIUM, power_id="power-small")
    run = run_sim(state, experimental=True)
    ev = _ev(run, "anomaly-power-low")
    assert ev.trigger["source"] == "design" and ev.trigger["ref"] == "architecture.powerId"
    assert ev.trigger["rule"] == "battery-reserve-low"
    assert ev.trigger["constraint_battery-reserve"] == "fail"
    assert ev.severity == "critical"
    assert ev.mission_day == state.operations.observation_plan[0].start_day


def test_coarse_adcs_triggers_pointing_drift(run_sim: RunFactory) -> None:
    run = run_sim(make_state(communications_id=MEDIUM, adcs_id="adcs-fine"))
    ev = _ev(run, "anomaly-pointing-drift")
    assert ev.trigger["ref"] == "architecture.adcsId"
    assert ev.trigger["rule"] == "pointing-out-of-spec"
    assert ev.trigger["analysis_pointing_ok"] is False
    assert isinstance(ev.trigger["value"], float) and ev.trigger["value"] > 1.0
    assert ev.severity == "warning"  # ratio 2.0 is not beyond the 2.0 severity selector


def test_low_propellant_headroom_triggers_correction_shortfall(run_sim: RunFactory) -> None:
    run = run_sim(
        make_state(communications_id=MEDIUM, propulsion_id="prop-cold-gas"), experimental=True
    )
    ev = _ev(run, "anomaly-correction-shortfall")
    assert ev.trigger["ref"] == "architecture.propulsionId"
    assert ev.trigger["constraint_delta-v-margin"] == "fail"
    assert ev.phase == "mid-course" and ev.severity == "critical"
    assert {c.id for c in ev.choices} == {"burn-reserve", "skip-correction", "abort-mission"}
    assert "headroom is already negative" in ev.description  # default burn-reserve warns


def test_every_scenario_layer_event_explains_why(run_sim: RunFactory) -> None:
    run = run_sim(make_state(communications_id=MEDIUM, adcs_id="adcs-fine"))
    for e in run.events:
        if e.id.startswith(("anomaly-", "scenario-")):
            assert e.trigger["source"] in ("design", "scenario-event")
            assert e.trigger["ref"] and e.trigger["rule"]
            assert "Why this happened" in e.description
            assert e.choices and e.resolved_by in {c.id for c in e.choices}


# --- the only randomness: the declared scenario event days -------------------------------


def test_scenario_event_days_are_seeded_inside_their_windows(run_sim: RunFactory) -> None:
    state = make_state(communications_id=MEDIUM)
    obs = state.operations.observation_plan
    solar_days, illum_days = set(), set()
    for seed in (1, 2, 3, 42):
        run = run_sim(state, seed=seed)
        a, b = _ev(run, SOLAR), _ev(run_sim(state, seed=seed), SOLAR)
        assert a == b
        assert obs[0].start_day <= a.mission_day <= obs[-1].start_day
        assert a.trigger["rule"] == "seeded-day" and a.trigger["window"] == "science-ops"
        ill = _ev(run, ILLUMINATION)
        assert ill.phase == "approach" and ill.trigger["window"] == "approach"
        solar_days.add(a.mission_day)
        illum_days.add(ill.mission_day)
    assert len(solar_days) > 1 and len(illum_days) > 1


def _unsequenced(events: list[MissionEvent]) -> list[dict[str, Any]]:
    """Events without ``sequence`` (a seeded event earlier in the log shifts the index)."""
    return [e.model_dump(exclude={"sequence"}) for e in events]


def _plan_items(run: MissionRun) -> list[str]:
    return sorted(
        str(e.trigger["plan_item"])
        for e in run.events
        if e.type in ("science", "downlink") and "plan_item" in e.trigger
    )


def test_different_seed_differs_only_in_seeded_events(run_sim: RunFactory) -> None:
    state = thin_downlink_state()
    a, b = run_sim(state, seed=1), run_sim(state, seed=2)
    assert _unsequenced(_design_anomalies(a)) == _unsequenced(_design_anomalies(b))
    assert _unsequenced([e for e in a.events if e.type == "milestone"]) == _unsequenced(
        [e for e in b.events if e.type == "milestone"]
    )
    assert _ev(a, SOLAR).mission_day != _ev(b, SOLAR).mission_day
    # every planned observation / contact is logged exactly once (flown, skipped or missed)
    planned = sorted(
        [f"operations.observationPlan[{i}]" for i in range(len(state.operations.observation_plan))]
        + [f"operations.downlinkPlan[{i}]" for i in range(len(state.operations.downlink_plan))]
    )
    assert _plan_items(a) == planned == _plan_items(b)
    # what differs is a scenario event, caused by one, or a planned item's data volume
    # after the earliest drawn day
    seeded = {SOLAR, ILLUMINATION}
    first = min(_ev(r, s).mission_day for r in (a, b) for s in seeded)
    a_ids = {e.id: e.model_dump(exclude={"sequence"}) for e in a.events}
    for e in b.events:
        if a_ids.get(e.id) != e.model_dump(exclude={"sequence"}):
            assert (
                e.id in seeded
                or e.trigger.get("caused_by") in seeded
                or (
                    e.type in ("science", "downlink")
                    and e.trigger.get("plan_item") in planned
                    and e.mission_day >= first
                )
            ), e.id
    # without seeded scenario events the seed changes nothing but the identity
    g1 = run_sim(state, seed=1, event_set=GENERIC_EVENTS).model_dump(mode="json")
    g2 = run_sim(state, seed=2, event_set=GENERIC_EVENTS).model_dump(mode="json")
    for key in ("run_id", "seed", "manifest", "input_snapshot"):
        g1.pop(key), g2.pop(key)
    assert g1 == g2


def test_generic_set_runs_every_starter(run_sim: RunFactory) -> None:
    for scenario in ("lunar-polar-scout", "earth-observation"):
        run = run_sim(make_state(scenario), event_set=GENERIC_EVENTS, experimental=True)
        assert run.final_report.outcome in ("success", "partial", "failure")
        assert "NaN" not in run.model_dump_json()

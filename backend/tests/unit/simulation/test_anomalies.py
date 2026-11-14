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
    load_event_sets,
    resolve_event_set,
)
from app.schemas.simulation import MissionEvent, MissionRun
from tests.unit.simulation.conftest import (
    EVENT_SET,
    GENERIC_EVENTS,
    MEDIUM,
    NEO_EVENTS,
    RunFactory,
    low_margin_state,
    make_state,
)

SOLAR = "scenario-solar-event"
MISSED = "anomaly-missed-contact"


def _ev(run: MissionRun, event_id: str) -> MissionEvent:
    found = [e for e in run.events if e.id == event_id]
    assert found, f"no event {event_id}: {[e.id for e in run.events if e.choices]}"
    return found[0]


def _design_anomalies(run: MissionRun) -> list[MissionEvent]:
    return [e for e in run.events if e.id.startswith("anomaly-")]


# --- event-set files ---------------------------------------------------------------------


def test_repo_event_sets_load(event_sets: Mapping[str, ScenarioEventSet]) -> None:
    assert {NEO_EVENTS, GENERIC_EVENTS, EVENT_SET} <= set(event_sets)
    neo = event_sets[NEO_EVENTS]
    assert neo.scenario_ids == ("neo-rendezvous",)
    assert [a.id for a in neo.anomalies] == [
        "missed-contact", "power-low", "pointing-drift", "correction-shortfall",
    ]  # fmt: skip
    assert [s.id for s in neo.scenario_events] == ["solar-event"]  # at most one
    assert not event_sets[EVENT_SET].anomalies and not event_sets[EVENT_SET].scenario_events
    assert not event_sets[GENERIC_EVENTS].scenario_events  # design rules only


def test_neo_event_file_is_named_per_scenario() -> None:
    raw = json.loads((DEFAULT_SCENARIOS_DIR / "neo-rendezvous.events.json").read_text("utf-8"))
    assert raw["eventSetId"] == NEO_EVENTS


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
        "rule": {"kind": "link-margin-below", "threshold": 6.0, "unit": "dB"},
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


# --- design-traced anomalies (no random punishment) --------------------------------------


def test_low_margin_comms_triggers_missed_contact_backlog(run_sim: RunFactory) -> None:
    state = low_margin_state()
    run = run_sim(state)
    ev = _ev(run, MISSED)
    assert ev.type == "anomaly" and ev.severity == "warning"
    trig = ev.trigger
    assert trig["source"] == "design" and trig["ref"] == "architecture.communicationsId"
    assert trig["rule"] == "link-margin-below" and trig["threshold_db"] == 6.0
    assert isinstance(trig["value_db"], float) and trig["value_db"] < 6.0
    assert trig["plan_item"] == "operations.downlinkPlan[0]"
    assert ev.mission_day == state.operations.downlink_plan[0].start_day
    assert "data backlog" in ev.description and "Why this happened" in ev.description
    assert len(ev.choices) >= 2
    # the missed pass is in the log and the backlog shows up in the buffer telemetry
    missed = [e for e in run.events if e.title.startswith("Ground contact 1 missed")]
    assert missed and missed[0].trigger["caused_by"] == MISSED
    nominal = run_sim(state, event_set=EVENT_SET)

    def peak(r: MissionRun) -> float:
        return max(t.value for t in r.telemetry if t.channel == "buffer_fill")

    assert peak(run) > peak(nominal)
    assert any(r.startswith("missed-contact ") for r in run.final_report.realized_risks)


@pytest.mark.parametrize(
    ("arch", "experimental"),
    [
        ({"communications_id": MEDIUM}, False),
        ({"communications_id": "comms-xband-highgain"}, True),  # budget fail only
        ({"communications_id": MEDIUM, "power_id": "power-xl"}, True),
    ],
)
def test_ample_margin_design_has_no_design_anomalies(
    run_sim: RunFactory, arch: dict[str, str], experimental: bool
) -> None:
    run = run_sim(make_state(**arch), experimental=experimental)
    assert _design_anomalies(run) == []
    choice_events = [e for e in run.events if e.choices]
    assert [e.id for e in choice_events] == [SOLAR]  # only the declared scenario event
    assert choice_events[0].trigger["source"] == "scenario-event"
    design_ids = ("missed-contact", "power-low", "pointing-drift", "correction-shortfall")
    assert not any(r.startswith(design_ids) for r in run.final_report.realized_risks)


def test_neo_low_margin_path_offers_two_decisions(run_sim: RunFactory) -> None:
    run = run_sim(low_margin_state())
    decisions = [e for e in run.events if e.choices]
    assert len(decisions) >= 2  # AC-10
    for e in decisions:
        assert 2 <= len(e.choices) <= 3
        assert len({tuple(sorted(c.effects.items())) for c in e.choices}) == len(e.choices)
        assert all(c.tradeoff for c in e.choices)


def test_low_battery_reserve_triggers_power_low(run_sim: RunFactory) -> None:
    state = make_state(communications_id=MEDIUM, power_id="power-small")
    run = run_sim(state, experimental=True)
    ev = _ev(run, "anomaly-power-low")
    assert ev.trigger["source"] == "design" and ev.trigger["ref"] == "architecture.powerId"
    assert ev.trigger["rule"] == "battery-reserve-below"
    assert ev.mission_day == state.operations.observation_plan[0].start_day


def test_coarse_adcs_triggers_pointing_drift(run_sim: RunFactory) -> None:
    run = run_sim(make_state(communications_id=MEDIUM, adcs_id="adcs-fine"))
    ev = _ev(run, "anomaly-pointing-drift")
    assert ev.trigger["ref"] == "architecture.adcsId"
    assert ev.trigger["rule"] == "pointing-ratio-above"
    assert isinstance(ev.trigger["value"], float) and ev.trigger["value"] > 0.5


def test_low_propellant_headroom_triggers_correction_shortfall(run_sim: RunFactory) -> None:
    run = run_sim(make_state(communications_id=MEDIUM, propulsion_id="prop-cold-gas"),
                  experimental=True)  # fmt: skip
    ev = _ev(run, "anomaly-correction-shortfall")
    assert ev.trigger["ref"] == "architecture.propulsionId"
    assert ev.phase == "mid-course"
    assert {c.id for c in ev.choices} == {"burn-reserve", "skip-correction", "abort-mission"}


def test_every_scenario_layer_event_explains_why(run_sim: RunFactory) -> None:
    run = run_sim(make_state(communications_id=MEDIUM, adcs_id="adcs-fine"))
    for e in run.events:
        if e.id.startswith(("anomaly-", "scenario-")):
            assert e.trigger["source"] in ("design", "scenario-event")
            assert e.trigger["ref"] and e.trigger["rule"]
            assert "Why this happened" in e.description
            assert e.choices and e.resolved_by in {c.id for c in e.choices}


# --- the only randomness: the declared scenario event day --------------------------------


def test_scenario_event_day_is_seeded_inside_science_window(run_sim: RunFactory) -> None:
    state = make_state(communications_id=MEDIUM)
    obs = state.operations.observation_plan
    days = set()
    for seed in (1, 2, 3, 42):
        a = _ev(run_sim(state, seed=seed), SOLAR)
        b = _ev(run_sim(state, seed=seed), SOLAR)
        assert a == b
        assert obs[0].start_day <= a.mission_day <= obs[-1].start_day
        assert a.trigger["rule"] == "seeded-day" and a.trigger["window"] == "science-ops"
        days.add(a.mission_day)
    assert len(days) > 1


def test_different_seed_differs_only_in_seeded_events(run_sim: RunFactory) -> None:
    state = low_margin_state()
    a, b = run_sim(state, seed=1), run_sim(state, seed=2)
    assert _design_anomalies(a) == _design_anomalies(b)
    assert [e for e in a.events if e.type == "milestone"] == [
        e for e in b.events if e.type == "milestone"
    ]
    assert _ev(a, SOLAR).mission_day != _ev(b, SOLAR).mission_day
    # every event that differs is the scenario event, caused by it, or data that flows on
    # from it (science / downlink volumes after the earlier of the two drawn days)
    first = min(_ev(a, SOLAR).mission_day, _ev(b, SOLAR).mission_day)
    a_ids = {e.id: e for e in a.events}
    for e in b.events:
        if a_ids.get(e.id) != e:
            assert (
                e.id == SOLAR
                or e.trigger.get("caused_by") == SOLAR
                or (e.type in ("science", "downlink") and e.mission_day >= first)
            ), e.id
    # without a seeded scenario event the seed changes nothing but the identity
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

"""Player decisions, effects pipeline, early termination and science outcome (Task 4.2)."""

import json
import os
import time
from pathlib import Path

import pytest

from app.domain.errors import DomainValidationError
from app.domain.simulation.decisions import (
    DEFAULT_RATIONALE,
    Decision,
    RunState,
    apply_decision,
)
from app.schemas.mission import MissionState
from app.schemas.simulation import DecisionChoice, MissionRun
from tests.unit.simulation.conftest import (
    MEDIUM,
    RunFactory,
    make_state,
    thin_downlink_state,
)
from tests.unit.simulation.test_runner import _approx_equal

SOLAR = "scenario-solar-event"
ILLUMINATION = "scenario-target-illumination"
MISSED = "anomaly-missed-contact"
SHORTFALL = "anomaly-correction-shortfall"
GOLDEN = Path(__file__).resolve().parents[2] / "golden" / "neo_run_anomaly_seed42.json"
GOLDEN_DECISIONS = {SOLAR: "continue", MISSED: "keep-rate", ILLUMINATION: "extend-observation"}


def _returned(run: MissionRun) -> tuple[float, ...]:
    return tuple(o.returned_fraction for o in run.science_outcomes)


def _cold_gas() -> MissionState:
    return make_state(communications_id=MEDIUM, propulsion_id="prop-cold-gas")


# --- apply_decision (unit) ---------------------------------------------------------------


def _decision() -> Decision:
    return Decision(
        event_id="scenario-x",
        mission_day=10.0,
        prompt="Pick one.",
        choices=(
            DecisionChoice(id="safe", label="Safe", tradeoff="slow", effects={"soc_delta": 0.0}),
            DecisionChoice(id="bold", label="Bold", tradeoff="risky", effects={"terminate": 1.0}),
        ),
    )


def test_apply_decision_records_and_applies_effects() -> None:
    state = RunState().with_pending(_decision())
    after = apply_decision(state, "scenario-x", "bold")
    assert after.pending == {}
    assert [(r.event_id, r.choice_id, r.decision_maker) for r in after.records] == [
        ("scenario-x", "bold", "player")
    ]
    assert after.applied[-1].effects["terminate"] == 1.0
    assert after.terminated is not None and after.terminated.mission_day == 10.0
    assert state.pending  # the input state is not mutated


def test_apply_decision_rejects_invalid_choice() -> None:
    state = RunState().with_pending(_decision())
    with pytest.raises(DomainValidationError) as exc:
        apply_decision(state, "scenario-x", "nope")
    assert exc.value.code == "INVALID_CHOICE"
    with pytest.raises(DomainValidationError) as exc:
        apply_decision(state, "scenario-y", "safe")
    assert exc.value.code == "UNKNOWN_DECISION_EVENT"


# --- run-level decisions ----------------------------------------------------------------


def test_invalid_choice_id_is_rejected(run_sim: RunFactory) -> None:
    with pytest.raises(DomainValidationError) as exc:
        run_sim(make_state(communications_id=MEDIUM), decisions={SOLAR: "panic"})
    assert exc.value.code == "INVALID_CHOICE"


def test_missing_decision_uses_documented_default(run_sim: RunFactory) -> None:
    run = run_sim(thin_downlink_state())
    choice_events = [e for e in run.events if e.choices]
    assert [r.event_id for r in run.decisions] == [e.id for e in choice_events]
    for rec, ev in zip(run.decisions, choice_events, strict=True):
        assert rec.choice_id == ev.choices[0].id == ev.resolved_by
        assert rec.decision_maker == "ground" and rec.rationale == DEFAULT_RATIONALE
        assert ev.decision_maker == "system"
        assert rec.mission_day == ev.mission_day
    assert run.final_report.outcome != "terminated"  # the safe branch keeps the journey


def test_player_decision_is_recorded(run_sim: RunFactory) -> None:
    run = run_sim(make_state(communications_id=MEDIUM), decisions={SOLAR: "continue"})
    by_event = {r.event_id: r for r in run.decisions}
    rec = by_event[SOLAR]
    assert (rec.event_id, rec.choice_id, rec.decision_maker) == (SOLAR, "continue", "player")
    assert by_event[ILLUMINATION].decision_maker == "ground"  # not chosen -> default
    ev = next(e for e in run.events if e.id == SOLAR)
    assert ev.resolved_by == "continue" and ev.decision_maker == "player"


def test_pause_science_vs_continue_differ_measurably(run_sim: RunFactory) -> None:
    state = make_state(communications_id=MEDIUM)
    pause = run_sim(state, decisions={SOLAR: "pause-science"})
    cont = run_sim(state, decisions={SOLAR: "continue"})
    assert _returned(pause) != _returned(cont)
    assert pause.final_report != cont.final_report
    assert pause.run_id != cont.run_id
    # pause skips observations; continue keeps them but takes the battery hit
    assert any(e.title.startswith("Observation skipped") for e in pause.events)
    assert not any(e.title.startswith("Observation skipped") for e in cont.events)
    day = next(e.mission_day for e in cont.events if e.id == SOLAR)
    soc = {(t.mission_day, t.channel): t.value for t in cont.telemetry}
    soc_pause = {(t.mission_day, t.channel): t.value for t in pause.telemetry}
    assert soc[(day, "battery_soc")] < soc_pause[(day, "battery_soc")]


def test_missed_contact_choices_change_the_backlog(run_sim: RunFactory) -> None:
    state = thin_downlink_state()
    lower = run_sim(state, decisions={MISSED: "lower-rate"})
    keep = run_sim(state, decisions={MISSED: "keep-rate"})

    def missed(r: MissionRun) -> int:
        return sum(1 for e in r.events if " missed" in e.title)

    assert missed(keep) > missed(lower)
    rates = {e.trigger.get("rate_bps") for e in lower.events if e.type == "downlink"}
    assert 25000.0 in rates  # the halved rate is flown after the anomaly


def test_propellant_choice_changes_telemetry(run_sim: RunFactory) -> None:
    burn = run_sim(_cold_gas(), experimental=True, decisions={SHORTFALL: "burn-reserve"})
    skip = run_sim(_cold_gas(), experimental=True, decisions={SHORTFALL: "skip-correction"})
    day = next(e.mission_day for e in burn.events if e.id == SHORTFALL)

    def prop(r: MissionRun) -> float:  # last propellant sample on the anomaly day
        return [
            t.value for t in r.telemetry
            if t.channel == "propellant_fraction" and t.mission_day == day
        ][-1]  # fmt: skip

    assert prop(burn) < prop(skip)
    ev = next(e for e in burn.events if e.id == SHORTFALL)
    assert "telemetry-only" in ev.description  # headroom is already negative


# --- early termination -----------------------------------------------------------------


def test_abort_path_terminates_with_postmortem(run_sim: RunFactory) -> None:
    run = run_sim(_cold_gas(), experimental=True, decisions={SHORTFALL: "abort-mission"})
    day = next(e.mission_day for e in run.events if e.id == SHORTFALL)
    assert run.phases[-1] == "terminated" and "complete" not in run.phases
    # intended exception to the six-phase rule: the abort in mid-course ends the phase list
    assert run.phases == (
        "launch-deployment", "commissioning", "cruise", "mid-course", "terminated",
    )  # fmt: skip
    assert run.phase_transitions[-1].phase == "terminated"
    assert run.phase_transitions[-1].mission_day == day
    last = run.events[-1]
    assert last.phase == "terminated" and last.severity == "critical"
    assert last.trigger["caused_by"] == SHORTFALL
    assert all(e.mission_day <= day for e in run.events)
    assert all(t.mission_day <= day for t in run.telemetry)
    report = run.final_report
    assert report.outcome == "terminated"
    assert "terminated" in report.summary.lower()
    assert any("correction" in c.lower() for c in report.root_causes)
    assert report.counterfactuals and report.limitations
    assert any("postmortem" in x.lower() for x in report.limitations)
    assert all(o.status == "missed" for o in run.science_outcomes)  # before science
    assert "NaN" not in run.model_dump_json()
    MissionRun.model_validate_json(run.model_dump_json())  # still a valid, reviewable run


def test_depleted_battery_terminates_the_run(run_sim: RunFactory) -> None:
    state = make_state(communications_id=MEDIUM, power_id="power-small")
    safe = run_sim(state, experimental=True)
    assert safe.final_report.outcome != "terminated"
    risky = run_sim(state, experimental=True, decisions={"anomaly-power-low": "continue-science"})
    assert risky.final_report.outcome == "terminated"
    assert risky.events[-1].trigger["cause"] == "battery-depleted"
    last_soc = [t for t in risky.telemetry if t.channel == "battery_soc"][-1]
    assert last_soc.phase == "terminated" and last_soc.value == 0.0  # keeps the dip


# --- reproducibility and golden -----------------------------------------------------------


def test_same_seed_and_decisions_are_byte_identical(run_sim: RunFactory) -> None:
    a = run_sim(thin_downlink_state(), decisions=GOLDEN_DECISIONS)
    b = run_sim(thin_downlink_state(), decisions=GOLDEN_DECISIONS)
    assert a.model_dump_json() == b.model_dump_json()
    assert a.run_id != run_sim(thin_downlink_state()).run_id  # decisions are part of the id


def test_anomaly_decision_run_matches_golden(run_sim: RunFactory) -> None:
    data = run_sim(thin_downlink_state(), decisions=GOLDEN_DECISIONS).model_dump(
        mode="json", by_alias=True
    )
    if os.environ.get("UPDATE_GOLDEN") == "1":
        if os.environ.get("CI"):
            pytest.fail("UPDATE_GOLDEN is not allowed in CI; golden files must be committed")
        text = json.dumps(data, indent=2) + "\n"
        GOLDEN.write_text(text, encoding="utf-8", newline="\n")
    assert GOLDEN.exists(), f"missing golden {GOLDEN.name}; run with UPDATE_GOLDEN=1"
    _approx_equal(data, json.loads(GOLDEN.read_text(encoding="utf-8")))


def test_decision_for_event_after_termination_is_rejected(run_sim: RunFactory) -> None:
    with pytest.raises(DomainValidationError) as exc:
        run_sim(
            _cold_gas(),
            experimental=True,
            decisions={SHORTFALL: "abort-mission", SOLAR: "continue"},
        )
    assert exc.value.code == "UNKNOWN_DECISION_EVENT"
    assert "ended earlier" in exc.value.message


def test_anomaly_path_runs_under_one_second(run_sim: RunFactory) -> None:
    start = time.perf_counter()
    run_sim(thin_downlink_state(), decisions=GOLDEN_DECISIONS)
    assert time.perf_counter() - start < 1.0


def test_illumination_choices_differ_measurably(run_sim: RunFactory) -> None:
    state = thin_downlink_state()
    keep = run_sim(state, decisions={ILLUMINATION: "keep-schedule"})
    extend = run_sim(state, decisions={ILLUMINATION: "extend-observation"})

    def series(r: MissionRun, channel: str) -> list[float]:
        return [t.value for t in r.telemetry if t.channel == channel]

    assert max(series(extend, "buffer_fill")) > max(series(keep, "buffer_fill"))
    assert min(series(extend, "propellant_fraction")) < min(series(keep, "propellant_fraction"))
    assert any(e.trigger.get("caused_by") == ILLUMINATION for e in extend.events)
    assert extend.final_report != keep.final_report


@pytest.mark.parametrize(
    ("scenario", "event_set", "alternatives"),
    [
        (
            "lunar-polar-scout",
            "lunar-default-v1",
            {"scenario-psr-pass": "heat-and-observe", "scenario-lunar-eclipse": "keep-operating"},
        ),
        (
            "earth-observation",
            "eo-default-v1",
            {
                "scenario-wildfire-tasking": "accept-tasking",
                "scenario-ground-station-outage": "reroute-backup",
            },
        ),
    ],
)
def test_lunar_and_eo_decisions_differ_measurably(
    run_sim: RunFactory, scenario: str, event_set: str, alternatives: dict[str, str]
) -> None:
    state = make_state(scenario)
    base = run_sim(state, event_set=event_set, experimental=True)
    for event_id, choice in alternatives.items():
        alt = run_sim(state, event_set=event_set, experimental=True, decisions={event_id: choice})
        assert alt.telemetry != base.telemetry or alt.science_outcomes != base.science_outcomes
        assert alt.final_report != base.final_report or alt.events != base.events
        assert alt.run_id != base.run_id

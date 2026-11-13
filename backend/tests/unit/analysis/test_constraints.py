from typing import Any

from app.domain.analysis.constraints import (
    CONSTRAINT_ASSUMPTIONS,
    evaluate_constraints,
    feasibility,
    mission_ready,
)
from app.domain.analysis.context import BATTERY_DISCHARGE_EFFICIENCY
from app.domain.analysis.drivers import top_drivers
from app.domain.analysis.mass import MassResult
from app.domain.analysis.propulsion import ManeuverBudget
from app.domain.analysis.score import score_preview
from app.domain.catalog.compat import CompatibilityIssue
from app.schemas.analysis import ConstraintResult
from tests.unit.analysis._ctx import cost, data, ledger, limits, link, make_ctx, thermal_ok


def by_id(**over: Any) -> dict[str, ConstraintResult]:
    return {c.id: c for c in evaluate_constraints(make_ctx(**over))}


def mass(wet: float, margin: float = 0.1, limit: float | None = 500.0) -> MassResult:
    alloc = wet * (1.0 + margin)
    return MassResult(
        payload_kg=1.0, subsystem_dry_kg=1.0, dry_kg=2.0, wet_kg=wet, allocated_kg=alloc,
        margin_to_limit_fraction=None if limit is None else (limit - alloc) / limit,
        top_contributors=(),
    )  # fmt: skip


def test_healthy_design_has_no_fail_or_warning() -> None:
    cs = evaluate_constraints(make_ctx())
    assert [c.status for c in cs if c.status in ("fail", "warning")] == []
    assert feasibility(cs) == "feasible" and mission_ready(cs)
    ids = [c.id for c in cs]
    for expected in (
        "mass-launch-limit", "mass-margin", "delta-v-margin", "peak-power", "energy-closure",
        "battery-reserve", "data-buffer", "link-margin", "data-return",
        "science-mandatory-coverage", "trajectory-valid", "budget", "thermal",
    ):  # fmt: skip
        assert expected in ids
    assert len(ids) == len(set(ids))


def test_mass_over_limit_is_infeasible_and_not_ready_ac04() -> None:
    ctx = make_ctx(mass=mass(600.0))
    cs = evaluate_constraints(ctx)
    c = {x.id: x for x in cs}["mass-launch-limit"]
    assert c.status == "fail" and c.severity == 3
    assert c.actual is not None and c.actual.unit == "kg" and c.actual.value == 660.0
    assert c.limit is not None and c.limit.value == 500.0
    assert c.actual.provenance.fidelity == "derived"
    assert "600" in c.explanation and "500" in c.explanation
    assert any(a.action_id == "larger-launch-vehicle" for a in c.suggested_actions)
    assert feasibility(cs) == "infeasible" and not mission_ready(cs)
    assert score_preview(ctx, cs).total > 0.0  # score still computed
    assert top_drivers(cs)[0] == "mass-launch-limit"


def test_ac04_allocated_over_limit_with_wet_within_is_infeasible() -> None:
    ctx = make_ctx(mass=mass(480.0))  # wet 480 <= 500 < allocated 528
    cs = evaluate_constraints(ctx)
    r = {c.id: c for c in cs}
    assert r["mass-launch-limit"].status == "fail"
    assert "528" in r["mass-launch-limit"].explanation
    assert r["mass-margin"].status == "not-modelled"
    assert feasibility(cs) == "infeasible" and not mission_ready(cs)
    full = make_ctx()
    ok_exec = score_preview(full, evaluate_constraints(full)).dimensions[1].score
    assert score_preview(ctx, cs).dimensions[1].score < ok_exec  # mission-execution reduced


def test_mass_margin_watch_band() -> None:
    r = by_id(mass=mass(436.0))  # allocated 479.6, margin 4.1% -> watch
    assert r["mass-launch-limit"].status == "pass"
    assert r["mass-margin"].status == "warning" and r["mass-margin"].severity == 2
    assert by_id(mass=mass(500.0 / 1.1 - 1e-6))["mass-margin"].status == "warning"  # margin 0
    assert by_id(mass=mass(400.0))["mass-margin"].status == "pass"  # 12%


def test_no_launch_limit_is_not_modelled_never_pass() -> None:
    r = by_id(limits=limits(launch_mass_limit_kg=None), mass=mass(300.0, limit=None))
    assert r["mass-launch-limit"].status == "not-modelled"
    assert r["mass-margin"].status == "not-modelled"
    assert r["mass-margin"].severity == 0


def test_delta_v_fail_names_actual_vs_limit() -> None:
    mb = ManeuverBudget(
        available_ms=1050.0, required_ms=1000.0, margin_ms=-50.0, per_maneuver=(),
        reserve_consumed_by="insertion", informational=(),
    )  # fmt: skip
    c = by_id(maneuvers=mb)["delta-v-margin"]  # reserve 100 m/s
    assert c.status == "fail"
    assert c.actual is not None and c.actual.unit == "m/s"
    assert c.limit is not None and c.limit.value == 1100.0
    assert "insertion" in c.explanation
    assert "add-propellant" in {a.action_id for a in c.suggested_actions}
    plain = ManeuverBudget(1050.0, 1000.0, -50.0, (), None, ())
    assert "insertion" not in by_id(maneuvers=plain)["delta-v-margin"].explanation


def test_peak_power_fail_warning_pass() -> None:
    assert by_id(peak_power_w=250.0)["peak-power"].status == "fail"
    assert by_id(peak_power_w=190.0)["peak-power"].status == "warning"  # 209 > 200
    assert by_id(peak_power_w=100.0)["peak-power"].status == "pass"
    z = by_id(peak_power_w=10.0, supply_power_w=0.0)["peak-power"]
    assert z.status == "fail" and z.margin_fraction == -1.0
    assert by_id(peak_power_w=0.0, supply_power_w=0.0)["peak-power"].status == "not-modelled"


def test_energy_closure_generation_shortfall_and_soc_are_separate_causes() -> None:
    short = by_id(energy=ledger(gen_wh=520.0, cons_wh=500.0))  # need 550
    assert short["energy-closure"].status == "fail"
    assert "520" in short["energy-closure"].explanation
    assert short["battery-reserve"].status == "pass"
    low_soc = by_id(energy=ledger(min_soc=0.1))
    assert low_soc["energy-closure"].status == "pass"  # no double failure for one cause
    assert low_soc["battery-reserve"].status == "fail"
    acts = {a.action_id for a in low_soc["battery-reserve"].suggested_actions}
    assert "larger-battery" in acts


def test_battery_reserve_warning_when_close_to_floor() -> None:
    r = by_id(energy=ledger(min_soc=0.25))  # 0.05 above floor < 0.1 margin
    assert r["battery-reserve"].status == "warning"
    assert r["energy-closure"].status == "pass"


def test_energy_without_consumption_is_not_modelled() -> None:
    c = by_id(energy=ledger(gen_wh=0.0, cons_wh=0.0))["energy-closure"]
    assert c.status == "not-modelled" and c.margin_fraction is None


def test_data_buffer_overflow_fail_unless_accepted() -> None:
    f = by_id(data=data(overflow=1000.0))["data-buffer"]
    assert f.status == "fail" and "overflow" in f.explanation
    w = by_id(data=data(overflow=1000.0), overflow_accepted=True)["data-buffer"]
    assert w.status == "warning" and "accepted" in w.explanation


def test_data_buffer_headroom_warning() -> None:
    c = by_id(data=data(peak=9.5e5))["data-buffer"]  # 5% headroom < 20%
    assert c.status == "warning" and c.severity == 1


def test_link_margin_partial_all_and_none() -> None:
    assert by_id(contact_links=(link(5.0), link(-3.0)))["link-margin"].status == "warning"
    all_bad = by_id(contact_links=(link(-22.0), link(-22.0)))["link-margin"]
    assert all_bad.status == "fail" and "-22.0" in all_bad.explanation
    assert by_id(contact_links=())["link-margin"].status == "not-modelled"


def test_data_return_warning_is_headline_neo_shortfall() -> None:
    d = data(generated=1.0e9, downlinked=2.0e8, capacity=2.5e8)
    c = by_id(data=d)["data-return"]
    assert c.status == "warning"
    assert "capacity" in c.explanation.lower()
    labels = " ".join(a.label for a in c.suggested_actions)
    assert (
        "Upgrade communications (e.g. higher-gain antenna) or reduce observation duty cycle"
        in labels
    )
    assert c.margin_fraction is not None and c.margin_fraction < 0
    assert "communications" in c.impacted_subsystems


def test_data_return_margin_zero_generated_and_undelivered_only() -> None:
    # capacity covers generated but not the required 20% margin
    d = data(generated=1.0e6, downlinked=1.0e6, capacity=1.1e6)
    c = by_id(data=d)["data-return"]
    assert c.status == "warning" and "below" in c.explanation
    z = by_id(data=data(generated=0.0, downlinked=0.0))["data-return"]
    assert z.status == "not-modelled" and z.margin_fraction is None
    # capacity is ample but some generated data never reaches a contact
    u = by_id(data=data(generated=1.0e6, downlinked=5.0e5, capacity=5.0e6))["data-return"]
    assert u.status == "warning"
    assert "covers" in u.explanation and "too early" in u.explanation
    assert "below" not in u.explanation


def test_compat_issue_each_becomes_a_failing_constraint() -> None:
    issues = (
        CompatibilityIssue("BUS_PAYLOAD", "inst-a", "instrument does not fit bus"),
        CompatibilityIssue("POWER_BUS", "pow-b", "power incompatible"),
    )
    r = by_id(compat_issues=issues)
    compat = [c for i, c in r.items() if i.startswith("compat-")]
    assert len(compat) == 2 and all(c.status == "fail" for c in compat)
    assert "compat-bus-payload-inst-a" in r
    assert compat[0].impacted_subsystems and compat[0].suggested_actions


def test_science_mandatory_coverage_levels() -> None:
    cap = by_id(science_missing=(("m1", "no-capability"),))["science-mandatory-coverage"]
    assert cap.status == "fail" and "m1" in cap.explanation


def test_science_not_returned_vs_not_collected() -> None:
    missing = (("m2", "no-returned-data"),)
    # data generated but none downlinked -> comms actions
    ret = by_id(science_missing=missing, data=data(generated=1.0e6, downlinked=0.0))[
        "science-mandatory-coverage"
    ]
    assert ret.status == "warning" and "not returned" not in ret.explanation
    assert "collected but no data is returned" in ret.explanation
    assert {a.action_id for a in ret.suggested_actions} == {"swap-comms", "add-contacts"}
    # data is being returned, so the requirement itself was never collected
    nc = by_id(science_missing=missing)["science-mandatory-coverage"]
    assert nc.status == "warning" and "not collected" in nc.explanation
    assert [a.action_id for a in nc.suggested_actions] == ["schedule-observation"]
    # nothing generated at all -> not collected
    none = by_id(science_missing=missing, data=data(generated=0.0, downlinked=0.0))
    assert "not collected" in none["science-mandatory-coverage"].explanation
    both = by_id(science_missing=missing, pointing_ok=False, power_ok=False)
    c = both["science-mandatory-coverage"]
    assert [a.action_id for a in c.suggested_actions] == [
        "schedule-observation", "upgrade-adcs", "increase-power",
    ]  # fmt: skip
    assert {"adcs", "power"} <= set(c.impacted_subsystems)


def test_science_no_required_measurements_not_modelled() -> None:
    c = by_id(required_measurement_ids=())["science-mandatory-coverage"]
    assert c.status == "not-modelled"


def test_science_minimum_score_and_success_probability() -> None:
    assert by_id()["science-minimum-score"].status == "not-modelled"
    w = by_id(limits=limits(minimum_science_score=90.0))["science-minimum-score"]
    assert w.status == "warning" and w.severity == 2 and w.suggested_actions
    assert w.actual is not None and w.actual.value == 80.0
    ok = by_id(limits=limits(minimum_science_score=80.0))["science-minimum-score"]
    assert ok.status == "pass"
    zero = by_id(limits=limits(minimum_science_score=0.0))["science-minimum-score"]
    assert zero.status == "pass" and zero.margin_fraction is None
    assert by_id()["success-probability"].status == "not-modelled"
    sp = by_id(limits=limits(minimum_success_probability=0.8))["success-probability"]
    assert sp.status == "not-modelled"
    assert sp.explanation == "requires robustness/simulation (later phase)"
    # soft: a science shortfall alone is marginal, never infeasible
    cs = evaluate_constraints(make_ctx(limits=limits(minimum_science_score=90.0)))
    assert feasibility(cs) == "marginal"


def test_trajectory_invalid_fails() -> None:
    c = by_id(trajectory_valid=False)["trajectory-valid"]
    assert c.status == "fail" and c.suggested_actions


def test_budget_fail_and_pass_margin() -> None:
    c = by_id(cost=cost(120.0e6))["budget"]
    assert c.status == "fail" and c.actual is not None and c.actual.unit == "USD"
    assert c.margin_fraction is not None and c.margin_fraction < 0
    ok = by_id()["budget"]
    assert ok.status == "pass" and ok.margin_fraction == 0.5


def test_thermal_passthrough_and_never_pass() -> None:
    warn = ConstraintResult(
        id="thermal", label="Thermal control", status="warning", severity=1,
        explanation="risk flag", impacted_subsystems=["thermal"],
    )  # fmt: skip
    cs = evaluate_constraints(make_ctx(thermal=warn))
    assert {c.id: c for c in cs}["thermal"] == warn
    assert feasibility(cs) == "marginal" and not mission_ready(cs)
    forced = ConstraintResult(
        id="thermal", label="Thermal control", status="pass", severity=0, explanation="ok"
    )
    t = {c.id: c for c in evaluate_constraints(make_ctx(thermal=forced))}["thermal"]
    assert t.status == "not-modelled"
    assert thermal_ok().status == "not-modelled"


def test_not_modelled_never_maps_to_pass_for_missing_inputs() -> None:
    cs = evaluate_constraints(
        make_ctx(
            contact_links=(),
            limits=limits(launch_mass_limit_kg=None),
            data=data(generated=0.0, downlinked=0.0),
            energy=ledger(gen_wh=0.0, cons_wh=0.0),
            peak_power_w=0.0,
            supply_power_w=0.0,
            required_measurement_ids=(),
        )
    )
    expected = {
        "link-margin", "mass-launch-limit", "mass-margin", "thermal", "data-return",
        "energy-closure", "peak-power", "science-mandatory-coverage",
        "science-minimum-score", "success-probability",
    }  # fmt: skip
    assert {c.id for c in cs if c.status == "not-modelled"} == expected


def test_every_fail_and_warning_is_explained_and_actionable() -> None:
    ctx = make_ctx(
        mass=mass(600.0),
        peak_power_w=250.0,
        energy=ledger(gen_wh=100.0, min_soc=0.1),
        data=data(generated=1.0e9, downlinked=1.0e8, capacity=1.0e8, overflow=5.0),
        contact_links=(link(-5.0),),
        science_missing=(("m1", "no-capability"),),
        trajectory_valid=False,
        compat_issues=(CompatibilityIssue("X", "c", "bad"),),
        maneuvers=ManeuverBudget(10.0, 1000.0, -990.0, (), None, ()),
        cost=cost(500.0e6),
    )
    cs = evaluate_constraints(ctx)
    flagged = [c for c in cs if c.status in ("fail", "warning")]
    assert len(flagged) >= 12
    for c in flagged:
        assert c.explanation.strip()
        assert len(c.impacted_subsystems) >= 1
        assert len(c.suggested_actions) >= 1
        assert c.severity == 3 if c.status == "fail" else c.severity in (1, 2)
    assert all(c.severity == 0 for c in cs if c.status in ("pass", "not-modelled"))


def test_marginal_is_not_mission_ready() -> None:
    cs = evaluate_constraints(make_ctx(peak_power_w=190.0))
    assert feasibility(cs) == "marginal" and not mission_ready(cs)


def test_exports() -> None:
    assert len(CONSTRAINT_ASSUMPTIONS) >= 5
    assert all(isinstance(s, str) and s for s in CONSTRAINT_ASSUMPTIONS)
    assert BATTERY_DISCHARGE_EFFICIENCY == 0.95

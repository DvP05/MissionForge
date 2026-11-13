import pytest
from pydantic import ValidationError

from app.domain.analysis.constraints import evaluate_constraints, feasibility, mission_ready
from app.domain.analysis.drivers import MAX_DRIVERS, top_drivers
from app.domain.analysis.mass import MassResult
from app.domain.analysis.propulsion import ManeuverBudget
from app.domain.analysis.score import SCORE_ASSUMPTIONS, WEIGHTS, score_preview
from app.schemas.analysis import ConstraintResult, ScoreBreakdown
from tests.unit.analysis._ctx import cost, data, ledger, limits, link, make_ctx, science


def dims(score: ScoreBreakdown) -> dict[str, float]:
    return {d.id: d.score for d in score.dimensions}


def expl(score: ScoreBreakdown) -> dict[str, str]:
    return {d.id: d.explanation for d in score.dimensions}


def test_weights_exact_and_sum_100() -> None:
    assert [w for _, w in WEIGHTS] == [30.0, 25.0, 20.0, 15.0, 10.0]
    assert sum(w for _, w in WEIGHTS) == 100.0
    ctx = make_ctx()
    s = score_preview(ctx, evaluate_constraints(ctx))
    assert [d.weight for d in s.dimensions] == [30.0, 25.0, 20.0, 15.0, 10.0]
    assert all(d.explanation.strip() for d in s.dimensions)
    assert all(0.0 <= d.score <= 100.0 for d in s.dimensions)
    assert s.total == pytest.approx(sum(d.weight * d.score / 100.0 for d in s.dimensions))
    assert len(SCORE_ASSUMPTIONS) >= 4


def test_scientific_return_is_coverage_score() -> None:
    ctx = make_ctx(science=science(63.0))
    assert dims(score_preview(ctx, evaluate_constraints(ctx)))["scientific-return"] == 63.0


def test_cost_alone_not_rewarded_within_budget() -> None:
    a, b = make_ctx(cost=cost(20.0e6)), make_ctx(cost=cost(90.0e6))
    sa = score_preview(a, evaluate_constraints(a))
    sb = score_preview(b, evaluate_constraints(b))
    assert dims(sa)["resource-stewardship"] == dims(sb)["resource-stewardship"] == 100.0
    assert sa.total == pytest.approx(sb.total)


def test_stewardship_falls_linearly_to_zero_at_double_budget() -> None:
    def steward(total: float) -> float:
        c = make_ctx(cost=cost(total))
        return dims(score_preview(c, evaluate_constraints(c)))["resource-stewardship"]

    assert steward(150.0e6) == pytest.approx(50.0)
    assert steward(200.0e6) == 0.0
    assert steward(500.0e6) == 0.0


def test_hard_fail_never_mission_ready_even_with_high_score_ac04() -> None:
    ctx = make_ctx(
        science=science(100.0),
        mass=MassResult(1.0, 1.0, 2.0, 600.0, 660.0, -0.32, ()),
    )
    cs = evaluate_constraints(ctx)
    s = score_preview(ctx, cs)
    assert feasibility(cs) == "infeasible" and not mission_ready(cs)
    assert s.total > 80.0  # score still computed and high; cannot grant readiness
    assert dims(s)["mission-execution"] < 100.0


def _cr(cid: str, status: str, sev: int) -> ConstraintResult:
    return ConstraintResult.model_validate(
        {
            "id": cid, "label": cid, "status": status, "severity": sev, "explanation": "e",
            "impacted_subsystems": ["x"] if status in ("fail", "warning") else [],
            "suggested_actions": (
                [{"action_id": "a", "label": "l", "expected_effect": "e"}]
                if status in ("fail", "warning")
                else []
            ),
        }
    )  # fmt: skip


def test_mission_execution_counts_gates() -> None:
    ctx = make_ctx()
    assert dims(score_preview(ctx, evaluate_constraints(ctx)))["mission-execution"] == 100.0
    bad = make_ctx(trajectory_valid=False)
    d = dims(score_preview(bad, evaluate_constraints(bad)))["mission-execution"]
    assert 0.0 < d < 100.0
    # warning counts half, fail zero, not-modelled and non-gates excluded
    cs = [
        _cr("budget", "warning", 1),
        _cr("peak-power", "fail", 3),
        _cr("trajectory-valid", "not-modelled", 0),
        _cr("mass-margin", "fail", 3),
        _cr("compat-x-y", "pass", 0),
    ]
    assert dims(score_preview(ctx, cs))["mission-execution"] == pytest.approx(50.0)
    assert dims(score_preview(ctx, []))["mission-execution"] == 0.0
    assert "proxy" in expl(score_preview(ctx, []))["mission-execution"]


def test_robustness_margins_relative_to_targets() -> None:
    ctx = make_ctx()  # all margins at/above target -> 100
    assert dims(score_preview(ctx, []))["engineering-robustness"] == pytest.approx(100.0)
    tight = make_ctx(
        energy=ledger(gen_wh=500.0, cons_wh=500.0),  # energy margin 0 -> 0 credit
        data=data(generated=1.0e6, downlinked=1.0e6, capacity=1.1e6),  # 0.1/0.2 -> 0.5
    )
    r = dims(score_preview(tight, []))["engineering-robustness"]
    assert r == pytest.approx(100.0 * (1.0 + 1.0 + 0.0 + 0.5) / 4.0)


def _only(**over: object) -> object:
    """Context whose only robustness credits come from the overridden inputs."""
    base: dict[str, object] = {
        "limits": limits(launch_mass_limit_kg=None),
        "energy": ledger(gen_wh=0.0, cons_wh=0.0),
        "data": data(generated=0.0, downlinked=0.0),
        "maneuvers": ManeuverBudget(2000.0, 1000.0, 900.0, (), None, ()),  # reserve 100
    }
    base.update(over)
    return make_ctx(**base)


def _rob(ctx: object) -> float:
    return dims(score_preview(ctx, []))["engineering-robustness"]  # type: ignore[arg-type]


def test_robustness_credit_full_at_gate_threshold_zero_at_no_headroom() -> None:
    # mass: limit 500, margin 0.1 -> allocated == limit (wet 500/1.1) gives full credit
    lim = limits()
    thr = _only(limits=lim, mass=MassResult(1.0, 1.0, 2.0, 500.0 / 1.1, 500.0, 0.0, ()))
    assert _rob(thr) == pytest.approx(100.0)  # (mass 1 + delta-v 1) / 2
    zero = _only(limits=lim, mass=MassResult(1.0, 1.0, 2.0, 500.0, 550.0, -0.1, ()))
    assert _rob(zero) == pytest.approx(50.0)  # mass 0, delta-v 1
    # delta-v: available == required + reserve -> 1; available == required -> 0
    assert _rob(_only(maneuvers=ManeuverBudget(1100.0, 1000.0, 0.0, (), None, ()))) == (
        pytest.approx(100.0)
    )
    assert _rob(_only(maneuvers=ManeuverBudget(1000.0, 1000.0, -100.0, (), None, ()))) == 0.0
    # energy: generated == consumed x (1 + margin) -> 1; generated == consumed -> 0
    assert _rob(_only(energy=ledger(gen_wh=550.0, cons_wh=500.0))) == pytest.approx(100.0)
    e0 = _only(energy=ledger(gen_wh=500.0, cons_wh=500.0))
    assert _rob(e0) == pytest.approx(50.0)  # energy 0, delta-v 1
    # data: capacity == generated x (1 + margin) -> 1; capacity == generated -> 0
    assert _rob(_only(data=data(1.0e6, 1.0e6, 1.2e6))) == pytest.approx(100.0)
    assert _rob(_only(data=data(1.0e6, 1.0e6, 1.0e6))) == pytest.approx(50.0)


def test_robustness_skips_unavailable_and_handles_zero_targets() -> None:
    ctx = make_ctx(
        limits=limits(
            launch_mass_limit_kg=None,
            power_margin_fraction=0.0,
            data_margin_fraction=0.0,
            delta_v_margin_km_per_s=0.0,
        ),
        mass=MassResult(1.0, 1.0, 2.0, 3.0, 3.0, None, ()),
        maneuvers=ManeuverBudget(100.0, 50.0, 50.0, (), None, ()),
        energy=ledger(gen_wh=0.0, cons_wh=0.0),
        data=data(generated=0.0, downlinked=0.0),
    )
    assert dims(score_preview(ctx, []))["engineering-robustness"] == 100.0
    neg = make_ctx(
        limits=limits(delta_v_margin_km_per_s=0.0),
        maneuvers=ManeuverBudget(100.0, 200.0, -100.0, (), None, ()),
    )
    assert dims(score_preview(neg, []))["engineering-robustness"] < 100.0


def test_operations_quality() -> None:
    full = make_ctx()
    assert dims(score_preview(full, []))["operations-quality"] == 100.0
    half = make_ctx(contact_links=(link(3.0), link(-1.0)))
    assert dims(score_preview(half, []))["operations-quality"] == 50.0
    over = score_preview(make_ctx(data=data(overflow=10.0)), [])
    assert dims(over)["operations-quality"] == 50.0
    assert "overflow" in expl(over)["operations-quality"]
    none = score_preview(make_ctx(contact_links=()), [])
    assert dims(none)["operations-quality"] == 0.0
    assert "proxy" in expl(none)["operations-quality"]


def test_over_budget_penalised_and_proxies_documented() -> None:
    ctx = make_ctx(cost=cost(150.0e6))
    s = score_preview(ctx, evaluate_constraints(ctx))
    assert dims(s)["resource-stewardship"] == pytest.approx(50.0)
    assert "design-time proxy; refined by simulation" in expl(s)["mission-execution"]
    assert "design-time proxy; refined by simulation" in expl(s)["operations-quality"]


def test_breakdown_contract_rejects_missing_dimension() -> None:
    s = score_preview(make_ctx(), [])
    with pytest.raises(ValidationError):
        ScoreBreakdown(total=1.0, dimensions=s.dimensions[:4])


def _c(cid: str, status: str, sev: int, margin: float | None) -> ConstraintResult:
    return ConstraintResult.model_validate(
        {
            "id": cid, "label": cid, "status": status, "severity": sev, "explanation": "e",
            "margin_fraction": margin, "impacted_subsystems": ["x"],
            "suggested_actions": [{"action_id": "a", "label": "l", "expected_effect": "e"}],
        }
    )  # fmt: skip


def test_top_drivers_ordering_and_cap() -> None:
    ok = ConstraintResult(id="ok", label="ok", status="pass", severity=0, explanation="e")
    cs = [
        _c("w-big", "warning", 2, -0.5),
        _c("f-b", "fail", 3, -0.2),
        _c("f-a", "fail", 3, -0.2),
        _c("f-small", "fail", 3, -0.01),
        _c("f-none", "fail", 3, None),
        _c("w-small", "warning", 2, 0.01),
        ok,
    ]
    assert top_drivers(cs) == ["f-small", "f-a", "f-b", "f-none", "w-small"]
    assert len(top_drivers(cs)) == MAX_DRIVERS
    assert top_drivers([ok]) == []
    # fail outranks a higher-severity warning
    assert top_drivers([_c("w", "warning", 3, 0.0), _c("f", "fail", 3, 0.5)])[0] == "f"

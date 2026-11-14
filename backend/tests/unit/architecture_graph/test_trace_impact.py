"""trace_impact: what one design edit changed (architecture 19.1 behaviour 7)."""

from app.domain.architecture_graph import build_architecture_graph, trace_impact
from app.schemas.analysis import ConstraintResult, MissionAnalysis

from ._support import analyse, catalog, edit_arch, state


def _metrics(report: object) -> dict[str, tuple[float, float]]:
    return {m.metric: (m.before, m.after) for m in report.changed_metrics}  # type: ignore[attr-defined]


def test_no_edit_means_no_impact() -> None:
    s = state()
    a = analyse(s)
    report = trace_impact(a, a, build_architecture_graph(s, a, catalog()))
    assert report.changed_metrics == []
    assert report.newly_violated == [] and report.improved == []
    assert report.affected_objectives == []


def test_removing_spectrometer_affects_composition_objective() -> None:
    s = state()
    after_state = edit_arch(s, instrument_ids=("inst-hires-camera",))
    before, after = analyse(s), analyse(after_state)
    report = trace_impact(
        before,
        after,
        build_architecture_graph(after_state, after, catalog()),
        before_graph=build_architecture_graph(s, before, catalog()),
    )
    # Coverage was already 0 (data not returned); the requirement still flips to uncovered.
    assert report.affected_objectives == ["obj-composition"]
    assert "science-mandatory-coverage" in report.newly_violated
    metrics = _metrics(report)
    # Removing hardware lowers mass and power and changes science coverage.
    assert metrics["dryMassKg"][1] < metrics["dryMassKg"][0]
    assert metrics["averagePowerW"][1] < metrics["averagePowerW"][0]


def test_antenna_upgrade_improves_link_margin() -> None:
    """The starter design's documented fix: low-gain -> medium X-band radio."""
    s = state()
    fixed = edit_arch(s, communications_id="comms-xband-medium")
    before, after = analyse(s), analyse(fixed)
    report = trace_impact(before, after, build_architecture_graph(fixed, after, catalog()))
    assert "link-margin" in report.improved
    assert "link-margin" not in report.newly_violated
    assert "dataDownlinkedBits" in _metrics(report)
    # And the reverse edit reports the same constraint as newly violated.
    back = trace_impact(after, before, build_architecture_graph(s, before, catalog()))
    assert "link-margin" in back.newly_violated


def _with_constraints(a: MissionAnalysis, constraints: list[ConstraintResult]) -> MissionAnalysis:
    statuses = {c.status for c in constraints}
    feas = (
        "infeasible" if "fail" in statuses else "marginal" if "warning" in statuses else "feasible"
    )
    return a.model_copy(
        update={
            "constraints": constraints,
            "feasibility": feas,
            "mission_ready": feas == "feasible",
        }
    )


def test_constraint_rank_rules() -> None:
    s = state()
    a = analyse(s)
    g = build_architecture_graph(s, a, catalog())

    def c(cid: str, status: str) -> ConstraintResult:
        return ConstraintResult(id=cid, label=cid, status=status, severity=0, explanation="x")  # type: ignore[arg-type]

    before = _with_constraints(
        a,
        [
            c("a", "pass"),
            c("b", "warning"),
            c("d", "fail"),
            c("e", "not-modelled"),
            c("gone", "fail"),
        ],
    )
    after = _with_constraints(
        a, [c("a", "fail"), c("b", "pass"), c("d", "warning"), c("e", "pass"), c("new", "warning")]
    )
    report = trace_impact(before, after, g)
    assert report.newly_violated == ["a", "new"]
    assert report.improved == ["b", "d", "gone"]
    # not-modelled -> pass is neither better nor worse.
    assert "e" not in report.newly_violated + report.improved


def test_impact_is_deterministic() -> None:
    s = state()
    alt = edit_arch(s, communications_id="comms-xband-highgain")
    before, after = analyse(s), analyse(alt)
    g = build_architecture_graph(alt, after, catalog())
    assert trace_impact(before, after, g) == trace_impact(before, after, g)

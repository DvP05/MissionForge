import pytest

from app.domain.analysis.reliability import RELIABILITY_ASSUMPTIONS, reliability, rpn
from app.domain.errors import DomainValidationError
from app.schemas.analysis import ReliabilityAnalysis
from tests.unit.analysis._arch import arch, comp, mode


def test_product_and_contract() -> None:
    a = arch(
        bus=comp("bus", "bus", 1.0, [mode("b1", 0.1, 2), mode("b2", 0.2, 3)]),
        power=comp("pow", "power", 1.0, [mode("p1", 0.5, 1)]),
    )
    r = reliability(a)
    assert isinstance(r, ReliabilityAnalysis)
    assert r.nominal_reliability == pytest.approx(0.9 * 0.8 * 0.5)
    expected = (0.1 * 2 + 0.2 * 3 + 0.5 * 1) / (3 * 5)
    assert r.risk_index == pytest.approx(expected)
    assert 0.0 <= r.risk_index <= 1.0


def test_no_failure_modes() -> None:
    r = reliability(arch())
    assert r.nominal_reliability == 1.0
    assert r.risk_index == 0.0
    assert r.single_point_failures == []


def test_common_cause_and_independence_noted() -> None:
    joined = " ".join(RELIABILITY_ASSUMPTIONS).lower()
    assert "common-cause" in joined
    assert "independen" in joined


def test_single_point_failures() -> None:
    a = arch(
        bus=comp("bus", "bus", 1.0, [mode("b1", 0.1, 4)]),  # no mitigation -> SPF
        power=comp("pow", "power", 1.0, [mode("p1", 0.1, 5, ["cdh"])]),  # mitigated by cdh
        adcs=comp("adcs", "adcs", 1.0, [mode("a1", 0.1, 5, ["ghost"])]),  # unresolved -> SPF
        cdh=comp("cdh", "cdh", 1.0, [mode("c1", 0.1, 3)]),  # low severity
    )
    assert reliability(a).single_point_failures == ["adcs", "bus"]


def test_self_mitigation_does_not_count() -> None:
    a = arch(bus=comp("bus", "bus", 1.0, [mode("b1", 0.1, 5, ["bus"])]))
    assert reliability(a).single_point_failures == ["bus"]


def test_rpn_is_heuristic_not_probability() -> None:
    r = rpn(0.5, 4)
    assert r.value == pytest.approx(0.5 * 4 * 3)
    assert r.is_probability is False
    assert r.provenance.fidelity == "gameplay-estimate"
    assert "heuristic" in r.label.lower()
    assert rpn(0.5, 4, detectability=5).value == pytest.approx(10.0)
    for bad in ((1.5, 4), (0.5, 0), (0.5, 6)):
        with pytest.raises(DomainValidationError):
            rpn(*bad)
    with pytest.raises(DomainValidationError):
        rpn(0.5, 4, detectability=0)


def test_mitigation_by_tag_of_other_component() -> None:
    a = arch(
        bus=comp("bus", "bus", 1.0, [mode("b1", 0.1, 5, ["redundant-computer"])]),
        cdh=comp("cdh", "cdh", 1.0, tags=["redundant-computer"]),
    )
    assert reliability(a).single_point_failures == []


def test_mitigation_tag_only_on_own_component_still_spf() -> None:
    a = arch(
        bus=comp("bus", "bus", 1.0, [mode("b1", 0.1, 5, ["self-tag"])], tags=["self-tag"]),
    )
    assert reliability(a).single_point_failures == ["bus"]


def test_assumptions_describe_per_mode_mean() -> None:
    joined = " ".join(RELIABILITY_ASSUMPTIONS)
    assert "per-mode mean" in joined and "dilutes" in joined

import pytest

from app.domain.analysis.cost import CostParams, cost_estimate
from app.domain.errors import DomainValidationError
from tests.unit.analysis._arch import arch, comp

P = CostParams()


def test_total_is_sum_of_components() -> None:
    c = cost_estimate(arch(), 365.25, P)
    assert c.hardware == pytest.approx(2e6 + 5e5 + 3e5 + 2e5 + 4e5 + 1e5 + 1.5e5 + 2 * 2.5e5)
    assert c.launch == 1_000_000.0
    assert c.ground == pytest.approx(365_250.0)
    assert c.operations == pytest.approx(365.25 * P.ops_cost_per_day_usd)
    assert c.development == pytest.approx(P.development_fraction * c.hardware)
    sub = c.hardware + c.launch + c.operations + c.ground + c.development
    assert c.reserves == pytest.approx(P.reserve_fraction * sub)
    assert c.total == pytest.approx(sub + c.reserves)


def test_range_and_label() -> None:
    c = cost_estimate(arch(), 100.0, P)
    assert c.low <= c.total <= c.high
    assert c.provenance.fidelity == "gameplay-estimate"
    assert c.assumptions


def test_zero_instruments_and_bad_input() -> None:
    c = cost_estimate(arch(instruments=()), 0.0, P)
    assert c.ground == 0.0 and c.operations == 0.0
    with pytest.raises(DomainValidationError):
        cost_estimate(arch(), -1.0, P)
    with pytest.raises(DomainValidationError):
        cost_estimate(arch(bus=comp("bus", "bus", None)), 10.0, P)
    with pytest.raises(DomainValidationError):
        cost_estimate(arch(bus=comp("bus", "bus", -5.0)), 10.0, P)
    with pytest.raises(DomainValidationError):
        CostParams(low_factor=1.5)
    with pytest.raises(DomainValidationError):
        CostParams(high_factor=0.5)
    with pytest.raises(DomainValidationError):
        CostParams(ops_cost_per_day_usd=-1.0)

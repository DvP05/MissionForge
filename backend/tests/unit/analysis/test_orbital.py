import pytest

from app.domain.analysis.orbital import (
    ASSUMPTIONS,
    circular_orbit_period_s,
    circular_orbit_velocity_ms,
)
from app.domain.errors import DomainValidationError


def test_leo_500km() -> None:
    assert circular_orbit_period_s(500_000.0) == pytest.approx(5677.0, abs=3.0)
    assert circular_orbit_velocity_ms(500_000.0) == pytest.approx(7612.0, abs=5.0)


def test_assumptions_and_invalid() -> None:
    assert any("two-body" in a and "circular" in a for a in ASSUMPTIONS)
    with pytest.raises(DomainValidationError):
        circular_orbit_period_s(-7e6)
    with pytest.raises(DomainValidationError):
        circular_orbit_velocity_ms(float("nan"))
    assert circular_orbit_period_s(0.0) > 0

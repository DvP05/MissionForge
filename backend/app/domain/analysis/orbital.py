"""Circular Earth-orbit helpers (architecture §7.7). Pure, SI (m, s, m/s)."""

import math

from app.domain.errors import DomainValidationError
from app.domain.units.constants import MU_EARTH, R_EARTH
from app.domain.units.guards import require_finite

MODEL_ID = "orbit-v1"
ASSUMPTIONS: tuple[str, ...] = (
    "two-body, circular, point-mass Earth (no J2, drag or third-body effects).",
    "Altitude is measured above the WGS-84 equatorial radius.",
)


def _radius_m(altitude_m: float) -> float:
    alt = require_finite(altitude_m, "altitude_m")
    r = R_EARTH + alt
    if r <= 0.0:
        raise DomainValidationError(
            "INVALID_ALTITUDE", "altitude_m", "orbit radius must be positive"
        )
    return r


def circular_orbit_period_s(altitude_m: float) -> float:
    """T = 2*pi*sqrt(r^3/mu)."""
    r = _radius_m(altitude_m)
    return 2.0 * math.pi * math.sqrt(r**3 / MU_EARTH)


def circular_orbit_velocity_ms(altitude_m: float) -> float:
    """v = sqrt(mu/r)."""
    return math.sqrt(MU_EARTH / _radius_m(altitude_m))

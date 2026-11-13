"""Units: constants, conversions and guards (public API)."""

from app.domain.units import constants
from app.domain.units.conversions import (
    day_to_s,
    db_to_ratio,
    dbw_to_w,
    deg_to_rad,
    j_to_wh,
    km_to_m,
    kms_to_ms,
    m_to_km,
    ms_to_kms,
    rad_to_deg,
    ratio_to_db,
    s_to_day,
    to_si,
    w_to_dbw,
    wh_to_j,
)
from app.domain.units.guards import require_finite, require_fraction, require_positive

__all__ = [
    "constants",
    "day_to_s",
    "db_to_ratio",
    "dbw_to_w",
    "deg_to_rad",
    "j_to_wh",
    "km_to_m",
    "kms_to_ms",
    "m_to_km",
    "ms_to_kms",
    "rad_to_deg",
    "ratio_to_db",
    "require_finite",
    "require_fraction",
    "require_positive",
    "s_to_day",
    "to_si",
    "w_to_dbw",
    "wh_to_j",
]

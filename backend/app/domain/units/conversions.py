"""Unit conversions. All unit conversion in the engine lives here."""

import math

from app.domain.units.guards import require_finite, require_positive
from app.schemas.units import Quantity, Uncertainty, Unit

_KM = 1000.0
_WH = 3600.0
_DAY = 86400.0


def km_to_m(x: float) -> float:
    return require_finite(x, "km") * _KM


def m_to_km(x: float) -> float:
    return require_finite(x, "m") / _KM


def kms_to_ms(x: float) -> float:
    return require_finite(x, "km/s") * _KM


def ms_to_kms(x: float) -> float:
    return require_finite(x, "m/s") / _KM


def wh_to_j(x: float) -> float:
    return require_finite(x, "Wh") * _WH


def j_to_wh(x: float) -> float:
    return require_finite(x, "J") / _WH


def day_to_s(x: float) -> float:
    return require_finite(x, "day") * _DAY


def s_to_day(x: float) -> float:
    return require_finite(x, "s") / _DAY


def deg_to_rad(x: float) -> float:
    return math.radians(require_finite(x, "deg"))


def rad_to_deg(x: float) -> float:
    return math.degrees(require_finite(x, "rad"))


def db_to_ratio(db: float) -> float:
    """Power ratio from decibels."""
    return float(10.0 ** (require_finite(db, "dB") / 10.0))


def ratio_to_db(ratio: float) -> float:
    return 10.0 * math.log10(require_positive(ratio, "ratio"))


def dbw_to_w(dbw: float) -> float:
    return float(10.0 ** (require_finite(dbw, "dBW") / 10.0))


def w_to_dbw(w: float) -> float:
    return 10.0 * math.log10(require_positive(w, "W"))


# unit -> (SI unit, scale factor)
_TO_SI: dict[str, tuple[Unit, float]] = {
    "km": ("m", _KM),
    "km/s": ("m/s", _KM),
    "Wh": ("J", _WH),
    "day": ("s", _DAY),
    "deg": ("rad", math.pi / 180.0),
}


def _scale(v: float | None, factor: float) -> float | None:
    return None if v is None else v * factor


def to_si(q: Quantity) -> Quantity:
    """Return q expressed in SI; non-convertible/SI units pass through unchanged."""
    entry = _TO_SI.get(q.unit)
    if entry is None:
        return q.model_copy(deep=True)
    si_unit, f = entry
    u = q.uncertainty
    new_u = (
        None
        if u is None
        else Uncertainty(
            distribution=u.distribution,
            min=_scale(u.min, f),
            mode=_scale(u.mode, f),
            max=_scale(u.max, f),
            sigma=_scale(u.sigma, f),
        )
    )
    return Quantity(
        value=q.value * f,
        unit=si_unit,
        provenance=q.provenance.model_copy(deep=True),
        uncertainty=new_u,
    )

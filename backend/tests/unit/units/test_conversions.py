import math
from collections.abc import Callable

import pytest
from pydantic import ValidationError

from app.domain.errors import DomainValidationError
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
from app.schemas.units import Provenance, Quantity, Uncertainty

PROV = Provenance(fidelity="derived", source_name="test", assumptions=["a"])


def test_known_answers() -> None:
    assert km_to_m(1.5) == 1500
    assert m_to_km(1500) == 1.5
    assert kms_to_ms(2.5) == 2500
    assert ms_to_kms(2500) == 2.5
    assert wh_to_j(1) == 3600
    assert j_to_wh(3600) == 1
    assert day_to_s(1) == 86400
    assert s_to_day(86400) == 1
    assert deg_to_rad(180) == pytest.approx(math.pi)
    assert rad_to_deg(math.pi) == pytest.approx(180)
    assert ratio_to_db(100) == pytest.approx(20)
    assert db_to_ratio(3.0103) == pytest.approx(2, rel=1e-4)
    assert dbw_to_w(30) == pytest.approx(1000)
    assert dbw_to_w(0) == pytest.approx(1)
    assert w_to_dbw(1000) == pytest.approx(30)


PAIRS: list[tuple[Callable[[float], float], Callable[[float], float]]] = [
    (km_to_m, m_to_km),
    (kms_to_ms, ms_to_kms),
    (wh_to_j, j_to_wh),
    (day_to_s, s_to_day),
    (deg_to_rad, rad_to_deg),
    (ratio_to_db, db_to_ratio),
    (w_to_dbw, dbw_to_w),
]


@pytest.mark.parametrize("fwd,back", PAIRS)
@pytest.mark.parametrize("x", [0.001, 0.5, 1.0, 7.3, 1234.5, 9.9e6])
def test_round_trip(
    fwd: Callable[[float], float], back: Callable[[float], float], x: float
) -> None:
    assert back(fwd(x)) == pytest.approx(x, rel=1e-12)


@pytest.mark.parametrize("fn", [km_to_m, day_to_s, deg_to_rad, db_to_ratio])
def test_converters_reject_bad_input(fn: Callable[[float], float]) -> None:
    for bad in (float("nan"), float("inf")):
        with pytest.raises(DomainValidationError):
            fn(bad)
    with pytest.raises(DomainValidationError):
        fn(True)


@pytest.mark.parametrize("fn", [ratio_to_db, w_to_dbw])
def test_log_converters_require_positive(fn: Callable[[float], float]) -> None:
    for bad in (0.0, -1.0):
        with pytest.raises(DomainValidationError) as ei:
            fn(bad)
        assert ei.value.code == "NOT_POSITIVE"


def test_constants() -> None:
    assert constants.G0 == 9.80665
    assert constants.C == 299792458.0
    assert constants.KB == 1.380649e-23
    assert constants.MU_EARTH == 3.986004418e14
    assert constants.R_EARTH == 6378137.0
    assert constants.SOLAR_CONSTANT_W_M2 == 1361.0
    assert constants.AU_M == 149_597_870_700.0
    assert constants.SOLAR_CONSTANT_PROVENANCE.fidelity == "gameplay-estimate"


def test_to_si_km_preserves_provenance() -> None:
    q = Quantity(value=1, unit="km", provenance=PROV)
    r = to_si(q)
    assert r.value == 1000
    assert r.unit == "m"
    assert r.provenance == PROV
    assert r is not q
    assert q.unit == "km"


@pytest.mark.parametrize(
    "unit,value,si_unit,expected",
    [
        ("km/s", 2.5, "m/s", 2500.0),
        ("Wh", 1.0, "J", 3600.0),
        ("day", 1.0, "s", 86400.0),
        ("deg", 180.0, "rad", math.pi),
    ],
)
def test_to_si_all(unit: str, value: float, si_unit: str, expected: float) -> None:
    r = to_si(Quantity.model_validate({"value": value, "unit": unit, "provenance": PROV}))
    assert r.unit == si_unit
    assert r.value == pytest.approx(expected)


@pytest.mark.parametrize(
    "unit",
    ["kg", "m", "s", "W", "J", "bit/s", "bit", "Hz", "K", "rad", "m/s"]
    + ["dB", "dBW", "USD", "USD_2026", "%"],
)
def test_to_si_passthrough(unit: str) -> None:
    q = Quantity.model_validate({"value": 3.5, "unit": unit, "provenance": PROV})
    r = to_si(q)
    assert r.unit == unit
    assert r.value == 3.5
    assert r == q


def test_to_si_converts_uncertainty() -> None:
    u = Uncertainty(distribution="triangular", min=1.0, mode=2.0, max=3.0, sigma=0.5)
    r = to_si(Quantity(value=2, unit="km", provenance=PROV, uncertainty=u))
    assert r.uncertainty is not None
    got = (r.uncertainty.min, r.uncertainty.mode, r.uncertainty.max, r.uncertainty.sigma)
    assert got == (1000.0, 2000.0, 3000.0, 500.0)
    assert r.uncertainty.distribution == "triangular"
    assert u.min == 1.0  # original untouched
    partial = Uncertainty(distribution="normal", sigma=1.0)
    r2 = to_si(Quantity(value=1, unit="day", provenance=PROV, uncertainty=partial))
    assert r2.uncertainty is not None
    assert r2.uncertainty.min is None
    assert r2.uncertainty.sigma == 86400.0


def test_quantity_rejects_bad_values() -> None:
    for bad in (float("nan"), float("inf"), float("-inf"), "1.0", True):
        with pytest.raises(ValidationError):
            Quantity.model_validate({"value": bad, "unit": "m", "provenance": PROV})


def test_uncertainty_rejects_non_finite() -> None:
    with pytest.raises(ValidationError):
        Uncertainty(distribution="normal", sigma=float("nan"))
    with pytest.raises(ValidationError):
        Uncertainty(distribution="uniform", min=float("-inf"))


def test_quantity_camel_alias_and_extra_forbidden() -> None:
    payload = {"value": 1.0, "unit": "m", "provenance": {"fidelity": "derived", "sourceName": "t"}}
    q = Quantity.model_validate(payload)
    assert q.provenance.source_name == "t"
    assert "sourceName" in q.provenance.model_dump(by_alias=True)
    with pytest.raises(ValidationError):
        Quantity.model_validate({**payload, "x": 1})
    with pytest.raises(ValidationError):
        Quantity.model_validate({**payload, "unit": "parsec"})

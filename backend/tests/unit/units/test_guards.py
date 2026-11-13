import math

import pytest

from app.domain.errors import DomainValidationError
from app.domain.units.guards import require_finite, require_fraction, require_positive


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_require_finite_rejects_non_finite(bad: float) -> None:
    with pytest.raises(DomainValidationError) as ei:
        require_finite(bad, "x")
    assert ei.value.field == "x"
    assert ei.value.code == "NOT_FINITE"
    assert ei.value.message


@pytest.mark.parametrize("bad", [True, False, "1.0", None, [1.0]])
def test_guards_reject_non_numbers(bad: object) -> None:
    for guard in (require_finite, require_positive, require_fraction):
        with pytest.raises(DomainValidationError) as ei:
            guard(bad, "y")
        assert ei.value.code == "NOT_A_NUMBER"
        assert ei.value.field == "y"


def test_require_finite_returns_float() -> None:
    assert require_finite(3, "x") == 3.0
    assert isinstance(require_finite(3, "x"), float)


@pytest.mark.parametrize("bad", [0.0, -1.0, -1e-12])
def test_require_positive_rejects(bad: float) -> None:
    with pytest.raises(DomainValidationError) as ei:
        require_positive(bad, "m")
    assert ei.value.code == "NOT_POSITIVE"


def test_require_positive_non_finite_code() -> None:
    with pytest.raises(DomainValidationError) as ei:
        require_positive(math.nan, "m")
    assert ei.value.code == "NOT_FINITE"
    assert require_positive(0.5, "m") == 0.5


@pytest.mark.parametrize("bad", [-0.01, 1.01])
def test_require_fraction_rejects(bad: float) -> None:
    with pytest.raises(DomainValidationError) as ei:
        require_fraction(bad, "p")
    assert ei.value.code == "NOT_A_FRACTION"


@pytest.mark.parametrize("ok", [0.0, 0.5, 1.0])
def test_require_fraction_accepts(ok: float) -> None:
    assert require_fraction(ok, "p") == ok


def test_require_fraction_non_finite() -> None:
    with pytest.raises(DomainValidationError) as ei:
        require_fraction(math.inf, "p")
    assert ei.value.code == "NOT_FINITE"


def test_error_str_contains_fields() -> None:
    e = DomainValidationError("C", "f", "msg")
    assert "C" in str(e) and "f" in str(e) and "msg" in str(e)

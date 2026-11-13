"""Numeric input guards raising DomainValidationError."""

import math

from app.domain.errors import DomainValidationError


def require_finite(x: object, name: str) -> float:
    if isinstance(x, bool) or not isinstance(x, int | float):
        raise DomainValidationError("NOT_A_NUMBER", name, f"{name} must be a real number")
    value = float(x)
    if not math.isfinite(value):
        raise DomainValidationError("NOT_FINITE", name, f"{name} must be finite")
    return value


def require_positive(x: object, name: str) -> float:
    value = require_finite(x, name)
    if value <= 0.0:
        raise DomainValidationError("NOT_POSITIVE", name, f"{name} must be > 0")
    return value


def require_fraction(x: object, name: str) -> float:
    value = require_finite(x, name)
    if not 0.0 <= value <= 1.0:
        raise DomainValidationError("NOT_A_FRACTION", name, f"{name} must be within [0, 1]")
    return value

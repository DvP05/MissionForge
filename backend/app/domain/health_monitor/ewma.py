"""EWMA of telemetry residuals (architecture 19.7): EWMA_t = lam*r_t + (1-lam)*EWMA_(t-1)."""

from collections.abc import Sequence

from app.domain.errors import DomainValidationError


def ewma(residuals: Sequence[float], lam: float) -> list[float]:
    """Exponentially weighted moving average, starting from 0. ``lam`` in (0, 1]."""
    if not 0.0 < lam <= 1.0:
        raise DomainValidationError("INVALID_LAMBDA", "lam", "lam must be in (0, 1]")
    out: list[float] = []
    prev = 0.0
    for r in residuals:
        prev = lam * r + (1.0 - lam) * prev
        out.append(prev)
    return out

"""Wilson 95 % score interval for a binomial proportion (architecture 19.3)."""

import math

from app.domain.errors import DomainValidationError

Z_95 = 1.96


def wilson_interval(k: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Interval for k successes out of n trials, clamped to [0, 1]. Never NaN."""
    if n <= 0:
        raise DomainValidationError("INVALID_SAMPLE_COUNT", "n", "n must be at least 1")
    if not 0 <= k <= n:
        raise DomainValidationError("INVALID_SAMPLE_COUNT", "k", "k must be within 0..n")
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    # At k == 0 / k == n the exact bound is 0 / 1; avoid 0.9999999999999999 from rounding.
    lo = 0.0 if k == 0 else max(0.0, center - half)
    hi = 1.0 if k == n else min(1.0, center + half)
    return lo, hi

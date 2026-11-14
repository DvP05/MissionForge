"""Shannon entropy in bits (architecture 19.4)."""

import math
from collections.abc import Iterable


def entropy_bits(probabilities: Iterable[float]) -> float:
    """H = -sum p log2 p, ignoring zero terms. Never negative (rounding clamped at 0)."""
    h = -math.fsum(p * math.log2(p) for p in probabilities if p > 0)
    return max(0.0, h)

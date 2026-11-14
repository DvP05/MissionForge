"""Seeded, bounded distribution samplers (architecture 19.3).

Semantics (documented so nothing is clipped silently):
- uniform: min..max.
- triangular: min..max with the given mode.
- normal: mean/std_dev; when min and/or max are given the normal is *truncated* by
  rejection sampling (up to 1000 redraws from the same seeded stream). If every redraw
  falls outside the bounds the draw is reported as an error, never clamped.
"""

import hashlib
import random

from app.domain.errors import DomainValidationError
from app.schemas.uncertainty import DistributionSpec

_MAX_REDRAWS = 1000


def rng_for(seed: int, sample_index: int, parameter_id: str) -> random.Random:
    """Independent stream per (master seed, sample, parameter): order-independent."""
    digest = hashlib.sha256(f"{seed}:{sample_index}:{parameter_id}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def sample(dist: DistributionSpec, rng: random.Random) -> float:
    if dist.kind == "uniform":
        assert dist.min is not None and dist.max is not None  # schema-validated
        return rng.uniform(dist.min, dist.max)
    if dist.kind == "triangular":
        assert dist.min is not None and dist.max is not None and dist.mode is not None
        return rng.triangular(dist.min, dist.max, dist.mode)
    assert dist.mean is not None and dist.std_dev is not None
    lo = dist.min if dist.min is not None else float("-inf")
    hi = dist.max if dist.max is not None else float("inf")
    for _ in range(_MAX_REDRAWS):
        value = rng.gauss(dist.mean, dist.std_dev)
        if lo <= value <= hi:
            return value
    raise DomainValidationError(
        "DISTRIBUTION_UNSATISFIABLE",
        "distribution",
        "truncated normal bounds exclude almost all of the distribution",
    )

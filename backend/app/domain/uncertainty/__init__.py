"""Robustness lab (architecture 19.3, Task 6.3, module M11).

A seeded Monte Carlo robustness proxy over the simplified engine. It is not a
flight-qualified probabilistic risk assessment, a covariance propagator or chance-
constrained optimal control.
"""

from app.domain.uncertainty.paths import ALLOWED_PATHS, apply_samples
from app.domain.uncertainty.run_robustness import (
    DISCLAIMER,
    MAX_SAMPLES,
    RobustnessLimitExceeded,
    run_robustness,
)
from app.domain.uncertainty.samplers import rng_for, sample
from app.domain.uncertainty.wilson_interval import wilson_interval

__all__ = [
    "ALLOWED_PATHS",
    "DISCLAIMER",
    "MAX_SAMPLES",
    "RobustnessLimitExceeded",
    "apply_samples",
    "rng_for",
    "run_robustness",
    "sample",
    "wilson_interval",
]

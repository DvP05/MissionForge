"""Wilson interval and bounded samplers (Task 6.3)."""

import math

import pytest

from app.domain.errors import DomainValidationError
from app.domain.uncertainty import rng_for, sample, wilson_interval
from app.schemas.uncertainty import DistributionSpec


def test_wilson_known_values() -> None:
    lo, hi = wilson_interval(80, 100)
    assert lo == pytest.approx(0.7112, abs=5e-4) and hi == pytest.approx(0.8666, abs=5e-4)


def test_wilson_edges_never_nan() -> None:
    lo, hi = wilson_interval(0, 100)
    assert lo == 0.0 and hi == pytest.approx(0.0370, abs=5e-4)
    lo, hi = wilson_interval(100, 100)
    assert hi == 1.0 and lo == pytest.approx(0.9630, abs=5e-4)
    lo, hi = wilson_interval(1, 1)
    assert not math.isnan(lo) and hi == 1.0


@pytest.mark.parametrize(("k", "n"), [(0, 0), (1, 0), (-1, 5), (6, 5)])
def test_wilson_rejects_bad_counts(k: int, n: int) -> None:
    with pytest.raises(DomainValidationError):
        wilson_interval(k, n)


DISTS = [
    DistributionSpec(kind="uniform", min=0.8, max=1.2),
    DistributionSpec(kind="triangular", min=-2.0, mode=-0.5, max=0.0),
    DistributionSpec(kind="normal", mean=1.0, std_dev=0.02, min=0.94, max=1.06),
]


@pytest.mark.parametrize("dist", DISTS)
def test_samples_respect_bounds(dist: DistributionSpec) -> None:
    assert dist.min is not None and dist.max is not None
    values = [sample(dist, rng_for(7, i, "p")) for i in range(2000)]
    assert all(dist.min <= v <= dist.max for v in values)


def test_unbounded_normal_has_expected_mean() -> None:
    dist = DistributionSpec(kind="normal", mean=5.0, std_dev=1.0)
    values = [sample(dist, rng_for(1, i, "x")) for i in range(4000)]
    assert sum(values) / len(values) == pytest.approx(5.0, abs=0.1)


def test_same_seed_same_draw_and_streams_are_independent() -> None:
    d = DISTS[0]
    assert sample(d, rng_for(42, 3, "a")) == sample(d, rng_for(42, 3, "a"))
    assert sample(d, rng_for(42, 3, "a")) != sample(d, rng_for(42, 3, "b"))
    assert sample(d, rng_for(42, 3, "a")) != sample(d, rng_for(43, 3, "a"))


def test_unsatisfiable_truncated_normal_errors_not_clamps() -> None:
    dist = DistributionSpec(kind="normal", mean=0.0, std_dev=0.001, min=10.0, max=11.0)
    with pytest.raises(DomainValidationError) as err:
        sample(dist, rng_for(1, 0, "x"))
    assert err.value.code == "DISTRIBUTION_UNSATISFIABLE"

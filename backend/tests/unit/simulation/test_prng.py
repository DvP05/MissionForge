"""Seeded PRNG derivation (Task 4.1)."""

import hashlib

from app.domain.simulation.prng import derive_seed, make_rng


def test_seed_is_first_8_bytes_of_sha256() -> None:
    digest = hashlib.sha256(b"42:anomaly:battery").digest()
    assert derive_seed(42, "anomaly", "battery") == int.from_bytes(digest[:8], "big")
    assert derive_seed(7) == int.from_bytes(hashlib.sha256(b"7:").digest()[:8], "big")


def test_same_seed_and_labels_give_same_stream() -> None:
    a = make_rng(42, "x")
    b = make_rng(42, "x")
    assert [a.random() for _ in range(5)] == [b.random() for _ in range(5)]


def test_labels_and_seed_separate_streams() -> None:
    base = make_rng(42, "x").random()
    assert make_rng(42, "y").random() != base
    assert make_rng(43, "x").random() != base

"""Seeded PRNG streams (M14). The ONLY randomness source in the simulation.

Every stream is a ``random.Random`` seeded from SHA-256 of ``f"{seed}:{':'.join(labels)}"``
(first 8 bytes, big-endian), so a labelled stream (e.g. ``("anomaly", "battery")``) is
independent of how many numbers other streams have drawn and is stable across Python
versions and platforms.
"""

import hashlib
import random

Rng = random.Random  # the stream type other simulation modules annotate with


def derive_seed(master_seed: int, *labels: str) -> int:
    text = f"{master_seed}:{':'.join(labels)}"
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def make_rng(master_seed: int, *labels: str) -> random.Random:
    return random.Random(derive_seed(master_seed, *labels))


__all__ = ["Rng", "derive_seed", "make_rng"]

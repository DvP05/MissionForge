"""Pareto dominance on minimisation-normalised objective vectors (architecture 19.2)."""

from collections.abc import Mapping, Sequence

from app.domain.errors import DomainValidationError


def dominates(a: Sequence[float], b: Sequence[float]) -> bool:
    """True if `a` is no worse than `b` everywhere and strictly better somewhere."""
    if len(a) != len(b):
        raise DomainValidationError("OBJECTIVE_MISMATCH", "objectives", "vector lengths differ")
    return all(x <= y for x, y in zip(a, b, strict=True)) and any(
        x < y for x, y in zip(a, b, strict=True)
    )


def pareto_front(vectors: Mapping[str, Sequence[float]]) -> list[str]:
    """Ids of non-dominated vectors, in input order. Identical vectors are all kept."""
    ids = list(vectors)
    return [i for i in ids if not any(dominates(vectors[j], vectors[i]) for j in ids if j != i)]

"""RunStore bounded LRU (Task 4.3)."""

from app.services.simulation_service import RunStore


def test_lru_evicts_least_recently_used() -> None:
    store: RunStore[int] = RunStore(capacity=3)
    for k in "abc":
        store.put(k, ord(k))
    assert store.get("a") == ord("a")  # refresh a: b is now the oldest
    store.put("d", 4)
    assert store.get("b") is None
    assert [store.get(k) for k in "acd"] == [ord("a"), ord("c"), 4]
    assert len(store) == 3


def test_put_existing_key_replaces_without_growing() -> None:
    store: RunStore[int] = RunStore(capacity=2)
    store.put("a", 1)
    store.put("a", 2)
    assert len(store) == 1 and store.get("a") == 2


def test_capacity_must_be_positive() -> None:
    import pytest

    with pytest.raises(ValueError):
        RunStore(capacity=0)

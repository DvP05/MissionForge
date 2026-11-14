"""In-memory TTL cache that keeps stale entries for degraded fallback (architecture 10.2)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class Entry[V]:
    value: V
    stored_at: datetime
    expires_at: datetime


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TtlCache[V]:
    def __init__(self, clock: Callable[[], datetime] = _utc_now, max_entries: int = 256) -> None:
        self._clock = clock
        self._max = max_entries
        self._items: dict[str, Entry[V]] = {}

    def set(self, key: str, value: V, ttl_seconds: float) -> None:
        now = self._clock()
        if key not in self._items and len(self._items) >= self._max:
            oldest = min(self._items, key=lambda k: self._items[k].stored_at)
            del self._items[oldest]
        self._items[key] = Entry(value, now, now + timedelta(seconds=ttl_seconds))

    def get(self, key: str) -> Entry[V] | None:
        """Fresh entry only."""
        e = self._items.get(key)
        return e if e is not None and self._clock() < e.expires_at else None

    def get_stale(self, key: str) -> Entry[V] | None:
        """Any entry, fresh or expired (for a labelled degraded fallback)."""
        return self._items.get(key)

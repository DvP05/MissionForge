"""Concurrency-1 request queue (architecture 10.1: one request at a time to JPL)."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class SerialQueue:
    """Runs submitted coroutine factories one at a time, in arrival order."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.in_flight = 0
        self.max_in_flight = 0

    async def submit(self, factory: Callable[[], Awaitable[T]]) -> T:
        async with self._lock:
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
            try:
                return await factory()
            finally:
                self.in_flight -= 1

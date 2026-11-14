"""Backend-only JPL Mission Design API client (architecture 10.2, Task 5.2).

Typed parameters -> URL (httpx encodes them; no string concatenation), application
User-Agent, overall timeout, capped exponential backoff for 429 / 5xx / network errors,
Retry-After respected, other 4xx never retried. Logs mode, status, duration and version
only: never query values (they can identify what a player looked at).
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import httpx

from app.domain.errors import DomainValidationError

log = logging.getLogger("missionforge.jpl")

Sleep = Callable[[float], Awaitable[None]]
MAX_RETRY_AFTER_S = 60.0  # honour Retry-After, but never hang a player request longer


class JplError(DomainValidationError):
    def __init__(self, code: str, message: str, *, status: int | None = None) -> None:
        super().__init__(code, "jpl", message)
        self.status = status


def user_agent(app_version: str, contact: str) -> str:
    return f"MISSIONFORGE/{app_version} ({contact})"


class JplClient:
    def __init__(
        self,
        base_url: str,
        *,
        user_agent: str,
        timeout_s: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
        max_attempts: int = 4,
        base_backoff_s: float = 1.0,
        max_backoff_s: float = 16.0,
    ) -> None:
        self._base_url = base_url
        self._headers = {"User-Agent": user_agent, "Accept": "application/json"}
        self._timeout = timeout_s
        self._transport = transport
        self._sleep = sleep
        self._max_attempts = max_attempts
        self._base = base_backoff_s
        self._cap = max_backoff_s

    def _backoff(self, attempt: int, retry_after: str | None) -> float:
        """Capped exponential backoff, never shorter than the server's Retry-After."""
        wait = min(self._cap, self._base * (2.0**attempt))
        if retry_after is not None:
            try:
                wait = max(wait, min(float(retry_after), MAX_RETRY_AFTER_S))
            except ValueError:
                pass
        return wait

    async def fetch(self, mode: str, params: Mapping[str, Any]) -> dict[str, Any]:
        last: JplError | None = None
        async with httpx.AsyncClient(
            transport=self._transport, timeout=self._timeout, headers=self._headers
        ) as client:
            for attempt in range(self._max_attempts):
                started = time.perf_counter()
                try:
                    resp = await client.get(self._base_url, params=dict(params))
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    last = JplError("JPL_UNAVAILABLE", f"JPL request failed: {type(exc).__name__}")
                    log.info("jpl mode=%s error=%s attempt=%d", mode, type(exc).__name__, attempt)
                    await self._sleep(self._backoff(attempt, None))
                    continue
                ms = (time.perf_counter() - started) * 1000
                log.info(
                    "jpl mode=%s status=%d ms=%.0f attempt=%d", mode, resp.status_code, ms, attempt
                )
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except ValueError as exc:
                        raise JplError("JPL_SCHEMA_UNSUPPORTED", "JPL returned non-JSON") from exc
                    if not isinstance(data, dict):
                        raise JplError("JPL_SCHEMA_UNSUPPORTED", "JPL returned a non-object")
                    return data
                if resp.status_code == 429:
                    last = JplError("JPL_RATE_LIMITED", "JPL asked us to slow down", status=429)
                    await self._sleep(self._backoff(attempt, resp.headers.get("Retry-After")))
                    continue
                if resp.status_code >= 500:
                    last = JplError(
                        "JPL_UNAVAILABLE", f"JPL error {resp.status_code}", status=resp.status_code
                    )
                    await self._sleep(self._backoff(attempt, resp.headers.get("Retry-After")))
                    continue
                # other 4xx: the request itself is wrong; retrying cannot help
                raise JplError(
                    "JPL_UNAVAILABLE",
                    f"JPL rejected the request ({resp.status_code})",
                    status=resp.status_code,
                )
        raise last or JplError("JPL_UNAVAILABLE", "JPL request failed")

"""JPL client + repository (Task 5.2). No network: httpx.MockTransport, synthetic data (R6)."""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.domain.errors import DomainValidationError
from app.infrastructure.cache.ttl_cache import TtlCache
from app.integrations.jpl.client import JplClient, JplError, user_agent
from app.integrations.jpl.repository import JplRepository, JplUnavailable, Snapshot
from app.schemas.trajectory import TrajectorySelection

FIX = Path(__file__).resolve().parents[2] / "fixtures" / "jpl"
MODE_A = json.loads((FIX / "mode_a_ok.json").read_text(encoding="utf-8"))
MODE_Q = json.loads((FIX / "mode_q_ok.json").read_text(encoding="utf-8"))
UA = user_agent("0.1.0", "team@example.org")
SNAP = Snapshot(
    synthetic=True,
    captured_at=None,
    note="test",
    mode_a=[({"crit": 1, "lim": 50, "year": "2031"}, MODE_A)],
    mode_q={"2031 SY1": MODE_Q},
)


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 14, 12, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


class Upstream:
    """Scripted JPL stand-in: a list of (status, body, headers) answers, last one repeats."""

    def __init__(self, *answers: tuple[int, Any, dict[str, str]], delay: float = 0.0) -> None:
        self.answers = list(answers)
        self.requests: list[httpx.Request] = []
        self.in_flight = 0
        self.max_in_flight = 0
        self.delay = delay

    async def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            status, body, headers = self.answers[min(len(self.requests) - 1, len(self.answers) - 1)]
            if status == 0:
                raise httpx.ConnectTimeout("timeout", request=request)
            return httpx.Response(status, json=body, headers=headers)
        finally:
            self.in_flight -= 1


def _repo(
    up: Upstream,
    *,
    live: bool = True,
    clock: Clock | None = None,
    sleeps: list[float] | None = None,
    max_attempts: int = 3,
) -> JplRepository:
    async def fake_sleep(s: float) -> None:
        if sleeps is not None:
            sleeps.append(s)

    client = JplClient(
        "https://ssd-api.jpl.nasa.gov/mdesign.api",
        user_agent=UA,
        transport=httpx.MockTransport(up.handler),
        sleep=fake_sleep,
        max_attempts=max_attempts,
    )
    return JplRepository(client=client, snapshot=SNAP, live_enabled=live, clock=clock or Clock())


def run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


def test_twenty_concurrent_identical_calls_hit_upstream_once_serially() -> None:
    up = Upstream((200, MODE_A, {}), delay=0.01)
    repo = _repo(up)

    async def go() -> list[Any]:
        return await asyncio.gather(*(repo.neo_accessible([2031], 1, 50) for _ in range(20)))

    results = run(go())
    assert len(up.requests) == 1 and up.max_in_flight == 1
    assert all(r.source.status in ("live", "cached") for r in results)


def test_different_params_are_serialised_one_at_a_time() -> None:
    up = Upstream((200, MODE_A, {}), delay=0.01)
    repo = _repo(up)

    async def go() -> None:
        await asyncio.gather(*(repo.neo_accessible([2030 + i], 1, 10) for i in range(1, 6)))

    run(go())
    assert len(up.requests) == 5 and up.max_in_flight == 1 and repo.queue.max_in_flight == 1


def test_user_agent_and_typed_params() -> None:
    up = Upstream((200, MODE_A, {}))
    run(_repo(up).neo_accessible([2031, 2030], 1, 50))
    req = up.requests[0]
    assert req.headers["User-Agent"] == "MISSIONFORGE/0.1.0 (team@example.org)"
    assert dict(req.url.params) == {"crit": "1", "year": "2030,2031", "lim": "50"}


def test_429_waits_for_retry_after_then_retries() -> None:
    up = Upstream((429, {}, {"Retry-After": "2"}), (200, MODE_A, {}))
    sleeps: list[float] = []
    out = run(_repo(up, sleeps=sleeps).neo_accessible([2031], 1, 50))
    assert out.source.status == "live" and len(up.requests) == 2
    assert sleeps and sleeps[0] >= 2


def test_backoff_is_capped_and_attempts_bounded() -> None:
    up = Upstream((503, {}, {}))
    sleeps: list[float] = []
    out = run(_repo(up, sleeps=sleeps, max_attempts=6).neo_accessible([2031], 1, 50))
    assert len(up.requests) == 6 and max(sleeps) <= 16
    assert sleeps == sorted(sleeps)
    assert out.source.status == "demo"  # nothing cached -> bundled snapshot


@pytest.mark.parametrize("status", [400, 404])
def test_client_errors_are_not_retried(status: int) -> None:
    up = Upstream((status, {}, {}))
    out = run(_repo(up).neo_accessible([2031], 1, 50))
    assert len(up.requests) == 1 and out.source.status == "demo"


def test_timeout_serves_stale_cache_labelled_cached() -> None:
    clock = Clock()
    up = Upstream((200, MODE_A, {}), (0, None, {}))
    repo = _repo(up, clock=clock)
    first = run(repo.neo_accessible([2031], 1, 50))
    assert first.source.status == "live"
    clock.now += timedelta(days=3)  # past the TTL
    second = run(repo.neo_accessible([2031], 1, 50))
    assert second.source.status == "cached" and "unavailable" in second.source.note
    assert second.source.retrieved_at == first.source.retrieved_at
    assert second.options == first.options


def test_no_cache_and_failure_serves_labelled_synthetic_snapshot() -> None:
    up = Upstream((0, None, {}))
    out = run(_repo(up).neo_accessible([2031], 1, 50))
    assert out.source.status == "demo" and out.source.synthetic
    assert "not JPL data" in out.source.note
    assert {o.source.fidelity for o in out.options} == {"gameplay-estimate"}


def test_unknown_version_falls_back_like_a_failure() -> None:
    bad = dict(MODE_A, signature={"version": "9.9"})
    out = run(_repo(Upstream((200, bad, {}))).neo_accessible([2031], 1, 50))
    assert out.source.status == "demo"


def test_live_disabled_never_calls_upstream() -> None:
    up = Upstream((200, MODE_A, {}))
    out = run(_repo(up, live=False).neo_accessible([2031], 1, 50))
    assert up.requests == [] and out.source.status == "demo"


@pytest.mark.parametrize("bad", ['"; rm -rf', "x" * 60, "", "../etc"])
def test_bad_designation_rejected_before_any_request(bad: str) -> None:
    up = Upstream((200, MODE_Q, {}))
    with pytest.raises(DomainValidationError):
        run(_repo(up).neo_detail(bad))
    assert up.requests == []


@pytest.mark.parametrize(
    ("years", "crit", "lim"), [([1999], 1, 10), ([2031], 9, 10), ([2031], 1, 500), ([], 1, 10)]
)
def test_bad_search_params_rejected_before_any_request(
    years: list[int], crit: int, lim: int
) -> None:
    up = Upstream((200, MODE_A, {}))
    with pytest.raises(DomainValidationError):
        run(_repo(up).neo_accessible(years, crit, lim))
    assert up.requests == []


def test_cache_key_includes_all_params() -> None:
    up = Upstream((200, MODE_A, {}))
    repo = _repo(up)
    run(repo.neo_accessible([2031], 1, 50))
    run(repo.neo_accessible([2031], 1, 50))
    run(repo.neo_accessible([2031], 2, 50))
    run(repo.neo_accessible([2031], 1, 40))
    assert len(up.requests) == 3


def test_mode_q_detail_live_and_offline() -> None:
    live = run(_repo(Upstream((200, MODE_Q, {}))).neo_detail("2031 SY1"))
    assert live.source.status == "live" and len(live.options) == 2
    offline = run(_repo(Upstream((0, None, {}))).neo_detail("2031 SY1"))
    assert offline.source.status == "demo"
    with pytest.raises(JplUnavailable):
        run(_repo(Upstream((0, None, {}))).neo_detail("2099 ZZ9"))


def test_logs_carry_no_query_values(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="missionforge.jpl")
    run(_repo(Upstream((200, MODE_Q, {}))).neo_detail("2031 SY1"))
    assert caplog.records and "SY1" not in caplog.text and "mode=Q" in caplog.text


def test_verify_requires_a_served_reference_and_matching_values() -> None:
    repo = _repo(Upstream((200, MODE_A, {})))
    opt = run(repo.neo_accessible([2031], 1, 50)).options[0]
    traj = TrajectorySelection(
        provider="jpl-mdesign", option_id=opt.designation, departure_date=opt.departure_date,
        arrival_date=opt.arrival_date, time_of_flight_days=opt.time_of_flight_days,
        c3_km2_per_s2=opt.c3_km2_per_s2,
        departure_v_infinity_km_per_s=opt.departure_v_infinity_km_per_s,
        arrival_v_infinity_km_per_s=opt.arrival_v_infinity_km_per_s,
        mission_delta_v_km_per_s=opt.total_delta_v_km_per_s, raw_source_ref=opt.source_ref,
    )  # fmt: skip
    assert repo.verify(traj) == opt
    forged = traj.model_copy(update={"c3_km2_per_s2": 1.0})
    assert repo.verify(forged) is None
    unknown = traj.model_copy(update={"raw_source_ref": "jpl-mdesign:deadbeef"})
    assert repo.verify(unknown) is None
    assert repo.verify(traj.model_copy(update={"provider": "scenario-preset"})) is None


def test_ttl_cache_fresh_and_stale() -> None:
    clock = Clock()
    cache: TtlCache[int] = TtlCache(clock, max_entries=2)
    cache.set("a", 1, 10)
    assert cache.get("a") is not None
    clock.now += timedelta(seconds=11)
    assert cache.get("a") is None and cache.get_stale("a") is not None
    cache.set("b", 2, 10)
    cache.set("c", 3, 10)  # evicts the oldest
    assert cache.get_stale("a") is None


def test_client_raises_typed_error_after_exhaustion() -> None:
    async def go() -> None:
        async def nosleep(_: float) -> None:
            return None

        c = JplClient("https://x", user_agent=UA, transport=httpx.MockTransport(
            lambda r: httpx.Response(503)), sleep=nosleep, max_attempts=2)  # fmt: skip
        await c.fetch("A", {})

    with pytest.raises(JplError) as err:
        run(go())
    assert err.value.code == "JPL_UNAVAILABLE"

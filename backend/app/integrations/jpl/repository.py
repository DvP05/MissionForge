"""JPL Mission Design repository (architecture 10.2, Task 5.2).

live -> fresh cache -> (fetch through the serial queue) -> stale cache -> bundled snapshot.

* Parameters are validated against allow-lists BEFORE any request.
* Cache keys include the mode and every parameter; identical concurrent requests share one
  upstream call.
* Live access is OFF unless explicitly enabled with a real contact address (ruling R6:
  automated agents and CI never call JPL). Offline, the bundled snapshot is served and
  labelled honestly: a SYNTHETIC fixture is never shown as JPL data.
* Every served option is recorded in a server-side registry keyed by ``source_ref``; a
  trajectory only becomes source-backed when its reference and values match a record
  (R48, replacing the R36 "never source-backed" rule).
"""

import asyncio
import json
import math
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from app.domain.errors import DomainValidationError
from app.infrastructure.cache.ttl_cache import TtlCache
from app.infrastructure.queue.serial_queue import SerialQueue
from app.integrations.jpl.client import JplClient, JplError
from app.integrations.jpl.normalize import (
    JPL_SOURCE_NAME,
    JplSchemaUnsupported,
    Normalized,
    normalize,
)
from app.schemas.space_data import (
    JplMissionOption,
    NeoAccessibleData,
    NeoDetailData,
    SourceInfo,
    SourceStatus,
)
from app.schemas.trajectory import TrajectorySelection
from app.schemas.units import Provenance

DESIGNATION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ()/'-]{0,39}$")
YEARS = range(2025, 2051)
CRITERIA = range(1, 7)
MAX_LIMIT = 100
MAX_YEARS = 5
JPL_API_URL = "https://ssd-api.jpl.nasa.gov/mdesign.api"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class JplUnavailable(DomainValidationError):  # noqa: N818
    def __init__(self, message: str) -> None:
        super().__init__("JPL_UNAVAILABLE", "jpl", message)


def validate_accessible(years: list[int], criterion: int, limit: int) -> dict[str, Any]:
    """Allow-listed query -> JPL mode A parameters (names per decision D6)."""
    if not years or len(years) > MAX_YEARS or any(y not in YEARS for y in years):
        raise DomainValidationError(
            "VALIDATION_ERROR",
            "years",
            f"1 to {MAX_YEARS} launch years in {YEARS.start}-{YEARS.stop - 1}",
        )
    if criterion not in CRITERIA:
        raise DomainValidationError("VALIDATION_ERROR", "criterion", "criterion must be 1 to 6")
    if not 1 <= limit <= MAX_LIMIT:
        raise DomainValidationError("VALIDATION_ERROR", "limit", f"limit must be 1 to {MAX_LIMIT}")
    return {"crit": criterion, "year": ",".join(str(y) for y in sorted(set(years))), "lim": limit}


def validate_designation(designation: str) -> dict[str, Any]:
    d = designation.strip()
    if not DESIGNATION_RE.fullmatch(d):
        raise DomainValidationError(
            "VALIDATION_ERROR", "designation", "letters, digits, spaces and ( ) / ' - only"
        )
    return {"sstr": d}


def cache_key(mode: str, params: Mapping[str, Any]) -> str:
    return mode + ":" + json.dumps(dict(sorted(params.items())), sort_keys=True)


@dataclass(frozen=True)
class Served:
    options: list[JplMissionOption]
    version: str
    retrieved_at: datetime
    skipped: int


@dataclass(frozen=True)
class Snapshot:
    """Bundled offline data. ``synthetic`` fixtures are labelled as NOT JPL data."""

    synthetic: bool
    captured_at: datetime | None
    note: str
    mode_a: list[tuple[dict[str, Any], dict[str, Any]]]  # (params, raw response)
    mode_q: dict[str, dict[str, Any]]  # designation -> raw response

    @staticmethod
    def load(path: Path) -> "Snapshot":
        doc = json.loads(path.read_text(encoding="utf-8"))
        captured = doc.get("capturedAt")
        return Snapshot(
            synthetic=bool(doc.get("synthetic", True)),
            captured_at=datetime.fromisoformat(captured) if captured else None,
            note=str(doc.get("note", "")),
            mode_a=[(dict(e["params"]), dict(e["response"])) for e in doc.get("modeA", [])],
            mode_q={str(k): dict(v) for k, v in doc.get("modeQ", {}).items()},
        )

    def provenance(self, version: str | None) -> Provenance:
        if self.synthetic:
            return Provenance(
                fidelity="gameplay-estimate",
                source_name="Synthetic JPL-shaped fixture (NOT JPL data)",
                source_version=version,
                assumptions=(
                    "Bundled offline example with invented values; replace it by running "
                    "scripts.capture_demo_data with your contact address.",
                ),
            )
        return Provenance(
            fidelity="source-backed",
            source_name=JPL_SOURCE_NAME,
            source_url=JPL_API_URL,
            source_version=version,
            retrieved_at=self.captured_at,
            assumptions=("Offline snapshot captured from the live API; may be out of date.",),
        )


Fetch = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


class JplRepository:
    def __init__(
        self,
        *,
        client: JplClient | None,
        snapshot: Snapshot,
        live_enabled: bool,
        ttl_a_s: float = 43200,
        ttl_q_s: float = 86400,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._client = client
        self._snapshot = snapshot
        self._live = live_enabled and client is not None
        self._ttl = {"A": ttl_a_s, "Q": ttl_q_s}
        self._clock = clock
        self._cache: TtlCache[Served] = TtlCache(clock)
        self._queue = SerialQueue()
        self._inflight: dict[str, asyncio.Future[Served]] = {}
        self._registry: dict[str, JplMissionOption] = {}
        self.upstream_calls = 0
        self._register_snapshot()

    @property
    def live_enabled(self) -> bool:
        return self._live

    @property
    def queue(self) -> SerialQueue:
        return self._queue

    def status_label(self) -> SourceStatus:
        return "live" if self._live else "demo"

    # --- snapshot ---------------------------------------------------------------------

    def _register_snapshot(self) -> None:
        for params, raw in self._snapshot.mode_a:
            try:
                for o in self._normalize_snapshot("A", params, raw).options:
                    self._registry[o.source_ref] = o
            except JplSchemaUnsupported:
                continue

    def _normalize_snapshot(
        self, mode: str, params: dict[str, Any], raw: dict[str, Any]
    ) -> Normalized:
        version = (raw.get("signature") or {}).get("version")
        prov = self._snapshot.provenance(version if isinstance(version, str) else None)
        if mode == "Q":
            return normalize(
                raw,
                mode="Q",
                params=params,
                provenance=prov,
                records_key="selectedMissions",
                default_object=raw.get("object"),
            )
        return normalize(raw, mode="A", params=params, provenance=prov)

    def _snapshot_info(self, version: str | None, skipped: int, extra: str) -> SourceInfo:
        snap = self._snapshot
        note = (
            "SYNTHETIC example, not JPL data: run scripts.capture_demo_data "
            "to capture a real snapshot."
            if snap.synthetic
            else f"Offline snapshot captured {snap.captured_at:%Y-%m-%d} from the JPL API."
            if snap.captured_at
            else "Offline snapshot from the JPL API."
        )
        return SourceInfo(
            status="demo",
            synthetic=snap.synthetic,
            retrieved_at=snap.captured_at,
            signature_version=version,
            note=(note + (" " + extra if extra else "")).strip(),
            skipped_rows=skipped,
        )

    # --- live path --------------------------------------------------------------------

    async def _fetch(self, mode: str, params: dict[str, Any]) -> Served:
        key = cache_key(mode, params)
        running = self._inflight.get(key)
        if running is not None:
            return await running
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Served] = loop.create_future()
        self._inflight[key] = fut
        try:
            served = await self._queue.submit(lambda: self._fetch_now(mode, params))
            fut.set_result(served)
            return served
        except BaseException as exc:
            fut.set_exception(exc)
            fut.exception()  # mark retrieved; waiters re-raise it
            raise
        finally:
            del self._inflight[key]

    async def _fetch_now(self, mode: str, params: dict[str, Any]) -> Served:
        assert self._client is not None
        fresh = self._cache.get(cache_key(mode, params))
        if fresh is not None:  # filled while this call waited in the queue
            return fresh.value
        self.upstream_calls += 1
        raw = await self._client.fetch(mode, params)
        now = self._clock()
        version = (raw.get("signature") or {}).get("version")
        prov = Provenance(
            fidelity="source-backed",
            source_name=JPL_SOURCE_NAME,
            source_url=JPL_API_URL,
            source_version=version if isinstance(version, str) else None,
            retrieved_at=now,
        )
        if mode == "Q":
            norm = normalize(
                raw,
                mode="Q",
                params=params,
                provenance=prov,
                records_key="selectedMissions",
                default_object=raw.get("object"),
            )
        else:
            norm = normalize(raw, mode="A", params=params, provenance=prov)
        served = Served(norm.options, norm.signature_version, now, norm.skipped_rows)
        self._cache.set(cache_key(mode, params), served, self._ttl[mode])
        for o in served.options:
            self._registry[o.source_ref] = o
        return served

    async def _resolve(self, mode: str, params: dict[str, Any]) -> tuple[Served, SourceInfo] | None:
        """Live or cached result, or None when only the snapshot is left."""
        key = cache_key(mode, params)
        fresh = self._cache.get(key)
        if fresh is not None:
            v = fresh.value
            return v, SourceInfo(
                status="cached",
                synthetic=False,
                retrieved_at=v.retrieved_at,
                signature_version=v.version,
                note="Cached JPL response.",
                skipped_rows=v.skipped,
            )
        if not self._live:
            return None
        try:
            v = await self._fetch(mode, params)
            return v, SourceInfo(
                status="live",
                synthetic=False,
                retrieved_at=v.retrieved_at,
                signature_version=v.version,
                note="Live JPL response.",
                skipped_rows=v.skipped,
            )
        except (JplError, JplSchemaUnsupported) as exc:
            stale = self._cache.get_stale(key)
            if stale is None:
                return None
            v = stale.value
            return v, SourceInfo(
                status="cached",
                synthetic=False,
                retrieved_at=v.retrieved_at,
                signature_version=v.version,
                skipped_rows=v.skipped,
                note=(
                    f"JPL unavailable ({exc.code}); showing cached data from "
                    f"{v.retrieved_at:%Y-%m-%d %H:%M} UTC."
                ),
            )

    # --- public API -------------------------------------------------------------------

    async def neo_accessible(
        self, years: list[int], criterion: int, limit: int
    ) -> NeoAccessibleData:
        params = validate_accessible(years, criterion, limit)
        got = await self._resolve("A", params)
        if got is not None:
            served, info = got
            return NeoAccessibleData(options=served.options[:limit], source=info)
        if not self._snapshot.mode_a:
            raise JplUnavailable("JPL is unreachable and no offline snapshot is bundled.")
        snap_params, raw = next(
            ((p, r) for p, r in self._snapshot.mode_a if p == params), self._snapshot.mode_a[0]
        )
        norm = self._normalize_snapshot("A", snap_params, raw)
        extra = (
            "" if snap_params == params else "The snapshot was captured for other search settings."
        )
        return NeoAccessibleData(
            options=norm.options[:limit],
            source=self._snapshot_info(norm.signature_version, norm.skipped_rows, extra),
        )

    async def neo_detail(self, designation: str) -> NeoDetailData:
        params = validate_designation(designation)
        got = await self._resolve("Q", params)
        if got is not None:
            served, info = got
            return NeoDetailData(designation=params["sstr"], options=served.options, source=info)
        raw = self._snapshot.mode_q.get(params["sstr"])
        if raw is None:
            raise JplUnavailable(f"No live JPL access and no offline data for {params['sstr']!r}.")
        norm = self._normalize_snapshot("Q", params, raw)
        for o in norm.options:
            self._registry[o.source_ref] = o
        return NeoDetailData(
            designation=params["sstr"],
            options=norm.options,
            source=self._snapshot_info(norm.signature_version, norm.skipped_rows, ""),
        )

    # --- provenance verification (R48) -------------------------------------------------

    def verify(self, trajectory: TrajectorySelection) -> JplMissionOption | None:
        """The served option behind this trajectory, if its reference and values match."""
        if trajectory.provider != "jpl-mdesign" or not trajectory.raw_source_ref:
            return None
        option = self._registry.get(trajectory.raw_source_ref)
        if option is None:
            return None
        pairs = [
            (trajectory.c3_km2_per_s2, option.c3_km2_per_s2),
            (trajectory.departure_v_infinity_km_per_s, option.departure_v_infinity_km_per_s),
            (trajectory.arrival_v_infinity_km_per_s, option.arrival_v_infinity_km_per_s),
            (trajectory.time_of_flight_days, option.time_of_flight_days),
        ]
        if any(a is None or not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9) for a, b in pairs):
            return None
        if trajectory.departure_date != option.departure_date:
            return None
        arrival: date | None = trajectory.arrival_date
        if arrival is not None and arrival != option.arrival_date:
            return None
        return option

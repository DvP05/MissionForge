"""Typed, server-only JPL mission-design client with demo fallback."""

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from app.config import Settings

SUPPORTED_VERSION = "1"


class SpaceDataRecord(BaseModel):
    designation: str
    name: str | None = None
    option_id: str
    departure_date: str | None = None
    arrival_date: str | None = None
    time_of_flight_days: float | None = None
    c3_km2_per_s2: float | None = None
    mission_delta_v_km_per_s: float | None = None
    source_url: str
    source_version: str
    fidelity: str


class SpaceDataResponse(BaseModel):
    status: str
    records: list[SpaceDataRecord]
    source_url: str
    source_version: str
    retrieved_at: str
    cache_ttl_seconds: int
    message: str | None = None


@dataclass
class _CacheEntry:
    expires_at: float
    response: SpaceDataResponse


class JplMDesignClient:
    def __init__(
        self,
        settings: Settings,
        *,
        snapshot_path: Path,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._snapshot_path = snapshot_path
        self._transport = transport
        self._cache: dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()

    def _demo(self, designation: str, message: str | None = None) -> SpaceDataResponse:
        payload = json.loads(self._snapshot_path.read_text(encoding="utf-8"))
        records = [
            SpaceDataRecord.model_validate(record)
            for record in payload["records"]
            if record["designation"].upper() == designation.upper()
        ]
        if not records:
            records = [
                SpaceDataRecord.model_validate(record)
                for record in payload["records"]
            ]
        return SpaceDataResponse(
            status="demo",
            records=records,
            source_url=payload["source_url"],
            source_version=payload["source_version"],
            retrieved_at=payload["captured_at"],
            cache_ttl_seconds=self._settings.jpl_cache_ttl_q_seconds,
            message=message,
        )

    def _normalize(self, payload: dict[str, Any], designation: str) -> SpaceDataResponse:
        signature = payload.get("signature")
        if not isinstance(signature, dict) or str(signature.get("version")) != SUPPORTED_VERSION:
            raise ValueError("Unsupported JPL response signature version.")
        raw_records = payload.get("records")
        if not isinstance(raw_records, list):
            raise ValueError("JPL response has no supported records array.")
        records = [
            SpaceDataRecord(
                designation=str(record.get("designation", designation)),
                name=record.get("name"),
                option_id=str(record.get("option_id", record.get("id", "jpl-option"))),
                departure_date=record.get("departure_date"),
                arrival_date=record.get("arrival_date"),
                time_of_flight_days=record.get("time_of_flight_days"),
                c3_km2_per_s2=record.get("c3_km2_per_s2"),
                mission_delta_v_km_per_s=record.get("mission_delta_v_km_per_s"),
                source_url=self._settings.jpl_mdesign_base_url,
                source_version=SUPPORTED_VERSION,
                fidelity="source-backed",
            )
            for record in raw_records
            if isinstance(record, dict)
        ]
        return SpaceDataResponse(
            status="live",
            records=records,
            source_url=self._settings.jpl_mdesign_base_url,
            source_version=SUPPORTED_VERSION,
            retrieved_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            cache_ttl_seconds=self._settings.jpl_cache_ttl_q_seconds,
        )

    def get(self, designation: str) -> SpaceDataResponse:
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(designation.upper())
            if cached and cached.expires_at > now:
                return cached.response.model_copy(update={"status": "cached"})
            try:
                headers = {
                    "User-Agent": (
                        f"{self._settings.app_name}/{self._settings.app_version} "
                        f"(contact: {self._settings.app_contact_email})"
                    )
                }
                with httpx.Client(
                    timeout=self._settings.jpl_request_timeout_ms / 1000,
                    transport=self._transport,
                ) as client:
                    response = client.get(
                        self._settings.jpl_mdesign_base_url,
                        params={"des": designation},
                        headers=headers,
                    )
                    response.raise_for_status()
                    result = self._normalize(response.json(), designation)
                self._cache[designation.upper()] = _CacheEntry(
                    expires_at=now + self._settings.jpl_cache_ttl_q_seconds,
                    response=result,
                )
                return result
            except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
                if cached:
                    return cached.response.model_copy(
                        update={"status": "cached", "message": f"Live source unavailable: {exc}"}
                    )
                return self._demo(designation, f"Live source unavailable: {exc}")

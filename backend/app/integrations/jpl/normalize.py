"""Normalise JPL Mission Design API payloads (architecture 10.4, Task 5.1).

Rows are read by FIELD NAME through one alias table, never by position. Each canonical field
lists the names it may carry; the exact JPL column names must be confirmed against a live
capture (decision D6): ``scripts.capture_demo_data`` runs this normaliser on every captured
response, so a naming mismatch fails loudly at capture time instead of at the demo.

Unsupported ``signature.version`` or a missing required field raises
``JplSchemaUnsupported`` (``JPL_SCHEMA_UNSUPPORTED``); the repository then falls back to
cache or the bundled snapshot. Rows shorter than ``fields`` are skipped and counted.
"""

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from app.domain.errors import DomainValidationError
from app.schemas.space_data import JplMissionOption
from app.schemas.units import Provenance

SUPPORTED_SIGNATURE_VERSIONS = frozenset({"1.2"})  # D6: confirm with the first live capture
JPL_SOURCE_NAME = "JPL SSD/CNEOS Small-Body Mission Design API"
JPL_DOC_URL = "https://ssd-api.jpl.nasa.gov/doc/mdesign.html"
MJD_EPOCH = date(1858, 11, 17)

# canonical field -> accepted JPL column names (first match wins)
ALIASES: dict[str, tuple[str, ...]] = {
    "designation": ("pdes", "des", "spkid"),
    "name": ("full_name", "fullname", "name"),
    "orbit_class": ("class", "orbit_class"),
    "absolute_magnitude": ("H", "h"),
    "orbit_condition_code": ("condition_code", "OC", "oc"),
    "is_near_earth_object": ("neo", "neo_flag"),
    "is_potentially_hazardous": ("pha", "pha_flag"),
    "is_binary": ("bin", "binary", "bin_flag"),
    "departure_date": ("date0", "dep_date", "date_dep"),
    "departure_mjd": ("MJD0", "mjd0"),
    "arrival_date": ("datef", "date1", "arr_date", "date_arr"),
    "arrival_mjd": ("MJDF", "MJDf", "mjdf", "MJD1"),
    "c3_km2_per_s2": ("c3", "c3_dep", "C3"),
    "departure_v_infinity_km_per_s": ("vinf_dep",),
    "arrival_v_infinity_km_per_s": ("vinf_arr",),
    "total_delta_v_km_per_s": ("dv_tot", "dv"),
    "time_of_flight_days": ("tof",),
}
REQUIRED = (
    "c3_km2_per_s2",
    "departure_v_infinity_km_per_s",
    "arrival_v_infinity_km_per_s",
    "total_delta_v_km_per_s",
    "time_of_flight_days",
)


class JplSchemaUnsupported(DomainValidationError):  # noqa: N818 - code names the error
    def __init__(self, field: str, message: str) -> None:
        super().__init__("JPL_SCHEMA_UNSUPPORTED", field, message)


@dataclass(frozen=True)
class Normalized:
    options: list[JplMissionOption]
    signature_version: str
    skipped_rows: int


def signature_version(raw: Mapping[str, Any]) -> str:
    sig = raw.get("signature")
    version = sig.get("version") if isinstance(sig, Mapping) else None
    if not isinstance(version, str) or version not in SUPPORTED_SIGNATURE_VERSIONS:
        raise JplSchemaUnsupported(
            "signature.version",
            f"unsupported JPL signature version {version!r} "
            f"(supported: {', '.join(sorted(SUPPORTED_SIGNATURE_VERSIONS))})",
        )
    return version


def _index(fields: Sequence[Any]) -> dict[str, int]:
    names = [str(f) for f in fields]
    out: dict[str, int] = {}
    for canonical, aliases in ALIASES.items():
        for a in aliases:
            if a in names:
                out[canonical] = names.index(a)
                break
    missing = [f for f in REQUIRED if f not in out]
    has_dates = ("departure_date" in out or "departure_mjd" in out) and (
        "arrival_date" in out or "arrival_mjd" in out
    )
    if missing or not has_dates:
        raise JplSchemaUnsupported(
            "fields",
            "required JPL fields not found: "
            + ", ".join(missing + ([] if has_dates else ["departure/arrival date"])),
        )
    return out


def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    x = float(v)
    if not math.isfinite(x):
        raise ValueError("non-finite")
    return x


def _flag(v: Any) -> bool:
    return str(v).strip().upper() in ("Y", "YES", "TRUE", "1")


def _date(row: Sequence[Any], idx: Mapping[str, int], name: str, mjd: str) -> date:
    if name in idx:
        text = str(row[idx[name]]).strip()
        for fmt in ("%Y-%m-%d", "%Y-%b-%d", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(text[: len("2031-Mar-01 00:00")], fmt).date()
            except ValueError:
                continue
        return date.fromisoformat(text[:10])
    value = _num(row[idx[mjd]])
    if value is None:
        raise ValueError("missing date")
    return MJD_EPOCH + timedelta(days=value)


def source_ref(mode: str, params: Mapping[str, Any], option: Mapping[str, Any]) -> str:
    """Stable server-side reference for one served option (verified later, R48)."""
    payload = json.dumps(
        {"mode": mode, "params": dict(sorted(params.items())), "option": option},
        sort_keys=True,
        default=str,
    )
    return "jpl-mdesign:" + hashlib.sha256(payload.encode()).hexdigest()[:24]


def normalize(
    raw: Mapping[str, Any],
    *,
    mode: str,
    params: Mapping[str, Any],
    provenance: Provenance,
    records_key: str = "records",
    default_object: Mapping[str, Any] | None = None,
) -> Normalized:
    """Normalise a ``fields`` + rows payload. ``default_object`` fills object-level fields
    (mode Q describes one object outside the rows)."""
    version = signature_version(raw)
    fields = raw.get("fields")
    rows = raw.get(records_key)
    if not isinstance(fields, list) or not isinstance(rows, list):
        raise JplSchemaUnsupported(records_key, f"expected 'fields' and '{records_key}' arrays")
    idx = _index(fields)
    obj = dict(default_object or {})
    options: list[JplMissionOption] = []
    skipped = 0
    for row in rows:
        if not isinstance(row, list) or len(row) < len(fields):
            skipped += 1
            continue

        def get(name: str, row: list[Any] = row) -> Any:
            return row[idx[name]] if name in idx else obj.get(name)

        try:
            values: dict[str, Any] = {
                "designation": str(get("designation") or "").strip(),
                "name": str(get("name") or get("designation") or "").strip(),
                "departure_date": _date(row, idx, "departure_date", "departure_mjd"),
                "arrival_date": _date(row, idx, "arrival_date", "arrival_mjd"),
                "orbit_class": str(get("orbit_class") or "unknown"),
                "absolute_magnitude": _num(get("absolute_magnitude")),
                "orbit_condition_code": _num(get("orbit_condition_code")),
                "is_near_earth_object": _flag(get("is_near_earth_object")),
                "is_potentially_hazardous": _flag(get("is_potentially_hazardous")),
                "is_binary": _flag(get("is_binary")),
            }
            for name in REQUIRED:
                v = _num(row[idx[name]])
                if v is None:
                    raise ValueError(f"missing {name}")
                values[name] = v
        except (ValueError, TypeError, IndexError):
            skipped += 1
            continue
        if not values["designation"]:
            skipped += 1
            continue
        ref = source_ref(mode, params, values)
        options.append(JplMissionOption(**values, source_ref=ref, source=provenance))
    return Normalized(options=options, signature_version=version, skipped_rows=skipped)

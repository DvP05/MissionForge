"""JPL normaliser (Task 5.1, architecture 10.4). Fixtures are SYNTHETIC (R6)."""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from app.integrations.jpl.normalize import (
    JplSchemaUnsupported,
    normalize,
    source_ref,
)
from app.schemas.units import Provenance

FIX = Path(__file__).resolve().parents[2] / "fixtures" / "jpl"
LIVE = Provenance(
    fidelity="source-backed",
    source_name="JPL SSD/CNEOS Small-Body Mission Design API",
    source_url="https://ssd-api.jpl.nasa.gov/mdesign.api",
    source_version="1.2",
    retrieved_at=datetime(2026, 11, 14, tzinfo=UTC),
)
PARAMS = {"crit": 1, "year": "2031", "lim": 50}


def _load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIX / name).read_text(encoding="utf-8"))
    return data


def test_mode_a_maps_by_field_name() -> None:
    out = normalize(_load("mode_a_ok.json"), mode="A", params=PARAMS, provenance=LIVE)
    assert out.signature_version == "1.2" and out.skipped_rows == 0
    first = out.options[0]
    assert first.designation == "2031 SY1"
    assert first.c3_km2_per_s2 == 14.0
    assert first.departure_v_infinity_km_per_s == 3.74
    assert first.arrival_v_infinity_km_per_s == 0.5
    assert first.total_delta_v_km_per_s == 4.62
    assert first.time_of_flight_days == 275.0
    assert first.departure_date == date(2031, 3, 1) and first.arrival_date == date(2031, 12, 1)
    assert first.is_near_earth_object and not first.is_potentially_hazardous
    assert out.options[2].is_binary


def test_reordered_fields_still_map_correctly() -> None:
    raw = _load("mode_a_ok.json")
    order = list(reversed(range(len(raw["fields"]))))
    raw["fields"] = [raw["fields"][i] for i in order]
    raw["records"] = [[row[i] for i in order] for row in raw["records"]]
    a = normalize(_load("mode_a_ok.json"), mode="A", params=PARAMS, provenance=LIVE).options
    b = normalize(raw, mode="A", params=PARAMS, provenance=LIVE).options
    assert a == b


def test_missing_required_field_is_unsupported() -> None:
    raw = _load("mode_a_ok.json")
    i = raw["fields"].index("dv_tot")
    raw["fields"][i] = "something_else"
    with pytest.raises(JplSchemaUnsupported) as err:
        normalize(raw, mode="A", params=PARAMS, provenance=LIVE)
    assert err.value.code == "JPL_SCHEMA_UNSUPPORTED" and "total_delta_v" in str(err.value)


def test_unknown_version_is_unsupported() -> None:
    with pytest.raises(JplSchemaUnsupported, match="9.9"):
        normalize(_load("unknown_version.json"), mode="A", params=PARAMS, provenance=LIVE)


def test_short_rows_are_skipped_and_counted() -> None:
    out = normalize(_load("short_row.json"), mode="A", params=PARAMS, provenance=LIVE)
    assert out.skipped_rows == 1 and len(out.options) == 2


def test_mode_q_object_fields_and_mjd_dates() -> None:
    raw = _load("mode_q_ok.json")
    out = normalize(
        raw, mode="Q", params={"des": "2031 SY1"}, provenance=LIVE,
        records_key="selectedMissions", default_object=raw["object"],
    )  # fmt: skip
    assert [o.designation for o in out.options] == ["2031 SY1", "2031 SY1"]
    assert out.options[0].departure_date == date(2031, 3, 1)
    assert out.options[0].time_of_flight_days == 275.0


def test_provenance_is_what_the_caller_stamps() -> None:
    synthetic = LIVE.model_copy(update={"fidelity": "gameplay-estimate"})
    live = normalize(_load("mode_a_ok.json"), mode="A", params=PARAMS, provenance=LIVE)
    demo = normalize(_load("mode_a_ok.json"), mode="A", params=PARAMS, provenance=synthetic)
    assert {o.source.fidelity for o in live.options} == {"source-backed"}
    assert {o.source.fidelity for o in demo.options} == {"gameplay-estimate"}


def test_source_ref_is_stable_and_parameter_sensitive() -> None:
    a = normalize(_load("mode_a_ok.json"), mode="A", params=PARAMS, provenance=LIVE)
    b = normalize(_load("mode_a_ok.json"), mode="A", params=PARAMS, provenance=LIVE)
    assert [o.source_ref for o in a.options] == [o.source_ref for o in b.options]
    assert source_ref("A", {"x": 1}, {"v": 1}) != source_ref("A", {"x": 2}, {"v": 1})
    assert all(o.source_ref.startswith("jpl-mdesign:") for o in a.options)

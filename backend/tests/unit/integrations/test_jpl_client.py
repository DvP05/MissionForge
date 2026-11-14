import json
from pathlib import Path

import httpx

from app.config import Settings
from app.integrations.jpl.client import JplMDesignClient


def _client(tmp_path: Path, payload: dict) -> JplMDesignClient:
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "source_url": "https://example.test",
                "source_version": "demo",
                "captured_at": "2026-01-01T00:00:00Z",
                "records": [],
            }
        ),
        encoding="utf-8",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return JplMDesignClient(
        Settings(jpl_mdesign_base_url="https://example.test"),
        snapshot_path=snapshot,
        transport=httpx.MockTransport(handler),
    )


def test_supported_signature_normalizes_records(tmp_path: Path) -> None:
    client = _client(
        tmp_path,
        {
            "signature": {"version": "1"},
            "records": [{"designation": "2024 AB", "id": "option-1", "time_of_flight_days": 10}],
        },
    )
    result = client.get("2024 AB")
    assert result.status == "live"
    assert result.records[0].option_id == "option-1"


def test_unknown_signature_uses_demo_fallback(tmp_path: Path) -> None:
    client = _client(tmp_path, {"signature": {"version": "unknown"}, "records": []})
    result = client.get("2024 AB")
    assert result.status == "demo"
    assert result.message and "Unsupported JPL response" in result.message


def test_second_request_uses_cache(tmp_path: Path) -> None:
    calls = 0
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "source_url": "https://example.test",
                "source_version": "demo",
                "captured_at": "2026-01-01T00:00:00Z",
                "records": [],
            }
        ),
        encoding="utf-8",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={"signature": {"version": "1"}, "records": [{"id": "option-1"}]},
        )

    client = JplMDesignClient(
        Settings(jpl_mdesign_base_url="https://example.test"),
        snapshot_path=snapshot,
        transport=httpx.MockTransport(handler),
    )
    assert client.get("2024 AB").status == "live"
    assert client.get("2024 AB").status == "cached"
    assert calls == 1

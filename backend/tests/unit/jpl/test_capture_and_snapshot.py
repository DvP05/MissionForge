"""Capture script and bundled snapshot (Task 5.3). JplClient.fetch is patched: no network (R6)."""

import json
from pathlib import Path
from typing import Any

import pytest

import scripts.capture_demo_data as capture
from app.config import DEFAULT_JPL_SNAPSHOT
from app.integrations.jpl.client import JplClient
from app.integrations.jpl.repository import Snapshot

FIX = Path(__file__).resolve().parents[2] / "fixtures" / "jpl"
MODE_A = json.loads((FIX / "mode_a_ok.json").read_text(encoding="utf-8"))
MODE_Q = json.loads((FIX / "mode_q_ok.json").read_text(encoding="utf-8"))


def test_bundled_snapshot_normalises_and_is_labelled() -> None:
    snap = Snapshot.load(DEFAULT_JPL_SNAPSHOT)
    assert snap.mode_a, "the bundled snapshot needs at least one mode A response"
    for params, raw in snap.mode_a:
        assert capture._check(raw, "A", params) > 0
    for des, raw in snap.mode_q.items():
        assert capture._check(raw, "Q", {"sstr": des}) > 0
    if snap.synthetic:
        assert "NOT JPL data" in snap.provenance("1.2").source_name
    else:
        assert snap.captured_at is not None


@pytest.mark.parametrize("contact", ["nobody", "team@example.com"])
def test_capture_refuses_placeholder_contact(contact: str) -> None:
    assert capture.main(["--contact", contact, "--dry-run"]) == 2


def _patch_fetch(monkeypatch: pytest.MonkeyPatch, mode_a: dict[str, Any]) -> list[str]:
    calls: list[str] = []

    async def fake_fetch(self: JplClient, mode: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append(mode)
        return mode_a if mode == "A" else MODE_Q

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(JplClient, "fetch", fake_fetch)
    monkeypatch.setattr(capture.asyncio, "sleep", no_sleep)
    return calls


def test_capture_writes_a_real_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = _patch_fetch(monkeypatch, MODE_A)
    out = tmp_path / "snap.json"
    monkeypatch.setattr(capture, "DEFAULT_JPL_SNAPSHOT", out)
    assert capture.main(["--contact", "me@university.edu", "--details", "2"]) == 0
    assert calls == ["A", "Q", "Q"]
    snap = Snapshot.load(out)
    assert snap.synthetic is False and snap.captured_at is not None
    assert snap.provenance("1.2").fidelity == "source-backed"


def test_capture_stops_without_writing_on_schema_mismatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_fetch(monkeypatch, dict(MODE_A, signature={"version": "2.0"}))
    out = tmp_path / "snap.json"
    monkeypatch.setattr(capture, "DEFAULT_JPL_SNAPSHOT", out)
    assert capture.main(["--contact", "me@university.edu"]) == 1
    assert not out.exists()

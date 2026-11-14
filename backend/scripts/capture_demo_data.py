"""Capture a REAL offline JPL snapshot for the demo (Task 5.3). Run it yourself.

Ruling R6: automated agents and CI never call JPL; a person runs this once, with their own
contact address in the User-Agent, following the JPL SSD API fair-use policy: requests are
sent one at a time, with a pause between them, through the same client the app uses.

    uv run python -m scripts.capture_demo_data --contact you@example.org
    uv run python -m scripts.capture_demo_data --contact you@example.org --years 2031 --dry-run

Every response is checked with the app's normaliser BEFORE anything is written. If JPL's
column names or signature version differ from what the normaliser expects (decision D6),
the script stops and prints what it saw, and the bundled snapshot is left untouched.
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from typing import Any

from app.config import DEFAULT_JPL_SNAPSHOT, get_settings
from app.integrations.jpl.client import JplClient, JplError, user_agent
from app.integrations.jpl.normalize import JplSchemaUnsupported, normalize
from app.integrations.jpl.repository import validate_accessible, validate_designation
from app.schemas.units import Provenance

PAUSE_S = 2.0  # between requests: one at a time, never a burst


def _check(raw: dict[str, Any], mode: str, params: dict[str, Any]) -> int:
    prov = Provenance(fidelity="source-backed", source_name="capture check")
    if mode == "Q":
        out = normalize(
            raw,
            mode="Q",
            params=params,
            provenance=prov,
            records_key="selectedMissions",
            default_object=raw.get("object"),
        )
    else:
        out = normalize(raw, mode="A", params=params, provenance=prov)
    return len(out.options)


async def capture(
    contact: str, years: list[int], criterion: int, limit: int, n_detail: int
) -> dict[str, Any]:
    settings = get_settings()
    client = JplClient(
        settings.jpl_mdesign_base_url,
        user_agent=user_agent(settings.app_version, contact),
        timeout_s=settings.jpl_request_timeout_ms / 1000,
    )
    a_params = validate_accessible(years, criterion, limit)
    raw_a = await client.fetch("A", a_params)
    print(f"mode A: signature {raw_a.get('signature')}, fields {raw_a.get('fields')}")
    n = _check(raw_a, "A", a_params)
    print(f"mode A: {n} options normalised")
    designations = []
    for row in raw_a.get("records", [])[:n_detail]:
        fields = raw_a["fields"]
        des = row[fields.index("pdes")] if "pdes" in fields else None
        if des:
            designations.append(str(des))
    mode_q: dict[str, Any] = {}
    for des in designations:
        await asyncio.sleep(PAUSE_S)
        q_params = validate_designation(des)
        raw_q = await client.fetch("Q", q_params)
        print(f"mode Q {des}: {_check(raw_q, 'Q', q_params)} options normalised")
        mode_q[q_params["sstr"]] = raw_q
    return {
        "synthetic": False,
        "capturedAt": datetime.now(UTC).isoformat(),
        "note": "Captured from the JPL SSD/CNEOS Small-Body Mission Design API for offline use.",
        "modeA": [{"params": a_params, "response": raw_a}],
        "modeQ": mode_q,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--contact", required=True, help="your email, sent in the User-Agent")
    ap.add_argument("--years", default="2031", help="comma-separated launch years")
    ap.add_argument("--criterion", type=int, default=1)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--details", type=int, default=3, help="mode Q lookups (one at a time)")
    ap.add_argument("--dry-run", action="store_true", help="check only; do not write")
    args = ap.parse_args(argv)
    if "@" not in args.contact or args.contact.endswith(("@example.com", "@example.org")):
        print("Give a real contact address; JPL asks automated clients to identify themselves.")
        return 2
    try:
        snap = asyncio.run(
            capture(
                args.contact,
                [int(y) for y in args.years.split(",")],
                args.criterion,
                args.limit,
                args.details,
            )  # fmt: skip
        )
    except (JplError, JplSchemaUnsupported) as exc:
        print(f"Capture failed ({exc.code}): {exc}. The bundled snapshot was not changed.")
        print(
            "If JPL renamed columns or bumped its version, update ALIASES / "
            "SUPPORTED_SIGNATURE_VERSIONS in app/integrations/jpl/normalize.py (decision D6)."
        )
        return 1
    if args.dry_run:
        print("Dry run: nothing written.")
        return 0
    DEFAULT_JPL_SNAPSHOT.write_text(
        json.dumps(snap, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"Wrote {DEFAULT_JPL_SNAPSHOT}. Restart the backend to serve it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

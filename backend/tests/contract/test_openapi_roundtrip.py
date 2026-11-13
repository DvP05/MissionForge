"""OpenAPI and response-envelope contract checks."""

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.main import create_app
from app.schemas.analysis import MissionAnalysis
from app.schemas.api import ApiMeta, ApiResult

OPENAPI_FILE = Path(__file__).resolve().parents[2] / "openapi.json"


def _refs(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                yield value
            else:
                yield from _refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _refs(item)


def test_every_route_referenced_schema_is_defined() -> None:
    spec = create_app().openapi()
    components = spec.get("components", {}).get("schemas", {})
    refs = set(_refs(spec))
    assert refs, "expected at least one schema reference"
    prefix = "#/components/schemas/"
    missing = sorted(r for r in refs if r.startswith(prefix) and r[len(prefix) :] not in components)
    assert not missing


def test_committed_openapi_matches_app() -> None:
    committed = json.loads(OPENAPI_FILE.read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(create_app().openapi()))


def test_api_result_generic_serialises_request_id(
    builders: dict[str, Callable[[], BaseModel]],
) -> None:
    analysis = builders["analysis.MissionAnalysis"]()
    assert isinstance(analysis, MissionAnalysis)
    result = ApiResult[MissionAnalysis](ok=True, data=analysis, meta=ApiMeta(request_id="req-42"))
    text = result.model_dump_json(by_alias=True)
    body = json.loads(text)
    assert body["meta"]["requestId"] == "req-42"
    assert body["meta"]["schemaVersion"] == "1.0"
    assert body["data"]["missionId"] == "mission-001"
    again = ApiResult[MissionAnalysis].model_validate_json(text)
    assert again == result

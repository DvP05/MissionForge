"""Schema-version migrations for raw MissionState dicts."""

import copy
from typing import Any

from app.domain.errors import DomainValidationError

CURRENT_SCHEMA_VERSION = "1.0"


class UnsupportedSchemaVersion(DomainValidationError):  # noqa: N818 - name fixed by spec
    def __init__(self, version: object) -> None:
        super().__init__(
            "UNSUPPORTED_SCHEMA_VERSION",
            "schemaVersion",
            f"unsupported mission schema version: {version!r}",
        )


def migrate_mission(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a raw mission dict at the current schema version (v1.0 is identity)."""
    version = raw.get("schemaVersion", raw.get("schema_version"))
    if version == CURRENT_SCHEMA_VERSION:
        return copy.deepcopy(raw)
    raise UnsupportedSchemaVersion(version)

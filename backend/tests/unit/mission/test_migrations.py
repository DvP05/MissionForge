import pytest

from app.domain.errors import DomainValidationError
from app.domain.mission.migrations import UnsupportedSchemaVersion, migrate_mission
from tests.unit.mission.test_mission_state import raw


def test_v1_identity_returns_copy() -> None:
    d = raw()
    out = migrate_mission(d)
    assert out == d
    assert out is not d
    out["title"] = "changed"
    assert d["title"] == "Test mission"


@pytest.mark.parametrize("version", ["2.0", None, 1, "0.9"])
def test_unsupported_version(version: object) -> None:
    d = raw()
    d["schemaVersion"] = version
    with pytest.raises(UnsupportedSchemaVersion) as ei:
        migrate_mission(d)
    assert ei.value.code == "UNSUPPORTED_SCHEMA_VERSION"
    assert isinstance(ei.value, DomainValidationError)


def test_missing_version() -> None:
    d = raw()
    del d["schemaVersion"]
    with pytest.raises(UnsupportedSchemaVersion):
        migrate_mission(d)

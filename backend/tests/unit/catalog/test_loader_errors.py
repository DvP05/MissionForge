"""Catalogue loader failure paths (Task 7.5 coverage): malformed data never loads silently."""

import json
from pathlib import Path

import pytest

from app.config import DEFAULT_CATALOG_DIR
from app.domain.catalog.loader import (
    MANIFEST_NAME,
    Catalog,
    CatalogLoadError,
    load_catalog,
    read_json,
)


def _real_component() -> dict[str, object]:
    manifest = read_json(DEFAULT_CATALOG_DIR / MANIFEST_NAME)
    doc = read_json(DEFAULT_CATALOG_DIR / manifest["files"][0])
    item: dict[str, object] = doc["components"][0]
    return item


def _write(tmp: Path, files: dict[str, object], manifest: object | None = None) -> Path:
    (tmp / MANIFEST_NAME).write_text(
        json.dumps(
            manifest if manifest is not None else {"catalogVersion": "t", "files": list(files)}
        ),
        encoding="utf-8",
    )
    for name, body in files.items():
        (tmp / name).write_text(json.dumps(body) if not isinstance(body, str) else body, "utf-8")
    return tmp


def test_missing_manifest_is_a_load_error(tmp_path: Path) -> None:
    with pytest.raises(CatalogLoadError) as err:
        load_catalog(tmp_path)
    assert err.value.code == "CATALOG_INVALID"


def test_nan_literal_is_rejected(tmp_path: Path) -> None:
    _write(tmp_path, {"a.json": '{"category": "bus", "components": [NaN]}'})
    with pytest.raises(CatalogLoadError, match="a.json"):
        load_catalog(tmp_path)


def test_category_mismatch_is_rejected(tmp_path: Path) -> None:
    item = _real_component()
    _write(tmp_path, {"a.json": {"category": "not-" + str(item["category"]), "components": [item]}})
    with pytest.raises(CatalogLoadError, match="category"):
        load_catalog(tmp_path)


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    item = _real_component()
    body = {"category": item["category"], "components": [item]}
    _write(tmp_path, {"a.json": body, "b.json": body})
    with pytest.raises(CatalogLoadError, match="duplicate"):
        load_catalog(tmp_path)


def test_catalog_mapping_api(tmp_path: Path) -> None:
    item = _real_component()
    _write(tmp_path, {"a.json": {"category": item["category"], "components": [item]}})
    cat = load_catalog(tmp_path)
    assert isinstance(cat, Catalog) and cat.version == "t" and len(cat) == 1
    cid = str(item["id"])
    assert cat.has(cid) and cat[cid].id == cid and list(cat) == [cid]
    assert cat.by_category(str(item["category"]))[0].id == cid
    assert cat.by_category("nothing") == ()

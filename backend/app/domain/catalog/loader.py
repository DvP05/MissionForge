"""Catalogue loader (M07): reads catalog_manifest.json and the category files it lists.

Takes an explicit directory (no environment access). The result is an immutable mapping
of component id -> CatalogComponent that satisfies the `CatalogLookup` protocol.
"""

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, NoReturn

from app.domain.errors import DomainValidationError
from app.schemas.catalog import CatalogComponent

MANIFEST_NAME = "catalog_manifest.json"


class CatalogLoadError(DomainValidationError):
    """The catalogue on disk is malformed (schema, duplicates, non-finite values)."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__("CATALOG_INVALID", field, message)


class Catalog(Mapping[str, CatalogComponent]):
    __slots__ = ("_by_category", "_items", "_version")

    def __init__(self, version: str, components: tuple[CatalogComponent, ...]) -> None:
        items: dict[str, CatalogComponent] = {}
        by_cat: dict[str, list[CatalogComponent]] = {}
        for c in components:
            if c.id in items:
                raise CatalogLoadError(c.id, f"duplicate component id {c.id!r}")
            items[c.id] = c
            by_cat.setdefault(c.category, []).append(c)
        self._version = version
        self._items = items
        self._by_category = {k: tuple(v) for k, v in by_cat.items()}

    @property
    def version(self) -> str:
        return self._version

    def has(self, component_id: str) -> bool:
        return component_id in self._items

    def by_category(self, category: str) -> tuple[CatalogComponent, ...]:
        return self._by_category.get(category, ())

    def __getitem__(self, key: str) -> CatalogComponent:
        return self._items[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)


def _reject_constant(name: str) -> NoReturn:
    raise ValueError(f"non-finite JSON literal {name}")


def read_json(path: Path) -> Any:
    """Parse JSON, rejecting NaN / Infinity literals."""
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_constant)


def load_catalog(path: Path) -> Catalog:
    try:
        manifest = read_json(path / MANIFEST_NAME)
        version = str(manifest["catalogVersion"])
        files = list(manifest["files"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise CatalogLoadError(MANIFEST_NAME, f"cannot read manifest: {exc}") from exc

    components: list[CatalogComponent] = []
    for fname in files:
        try:
            doc = read_json(path / fname)
            category = doc["category"]
            raw = doc["components"]
            for item in raw:
                comp = CatalogComponent.model_validate(item)
                if comp.category != category:
                    raise ValueError(f"{comp.id} category {comp.category!r} != file {category!r}")
                components.append(comp)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise CatalogLoadError(str(fname), f"invalid catalogue file: {exc}") from exc
    return Catalog(version, tuple(components))

"""Owns the catalogue: loaded once at startup, read-only afterwards."""

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from app.config import DEFAULT_CATALOG_DIR
from app.domain.catalog.loader import Catalog, load_catalog
from app.schemas.catalog import CatalogComponent
from app.schemas.units import Fidelity


@dataclass(frozen=True)
class SourceSummary:
    source_name: str
    source_url: str | None
    source_version: str | None
    fidelity: Fidelity
    component_count: int


class CatalogService:
    def __init__(self, catalog: Catalog) -> None:
        self._catalog = catalog

    @classmethod
    def from_directory(cls, path: Path = DEFAULT_CATALOG_DIR) -> "CatalogService":
        return cls(load_catalog(path))

    @property
    def catalog(self) -> Catalog:
        return self._catalog

    @property
    def version(self) -> str:
        return self._catalog.version

    def groups(self) -> list[tuple[str, list[CatalogComponent]]]:
        """Components grouped by category, in catalogue order."""
        grouped: dict[str, list[CatalogComponent]] = {}
        for comp in self._catalog.values():
            grouped.setdefault(comp.category, []).append(comp)
        return list(grouped.items())

    def sources(self) -> list[SourceSummary]:
        counts: Counter[tuple[str, str | None, str | None, Fidelity]] = Counter()
        for comp in self._catalog.values():
            p = comp.provenance
            counts[(p.source_name, p.source_url, p.source_version, p.fidelity)] += 1
        return [
            SourceSummary(name, url, ver, fid, n)
            for (name, url, ver, fid), n in sorted(counts.items(), key=lambda kv: str(kv[0]))
        ]

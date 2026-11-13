"""Resolve a SpacecraftArchitecture's component ids to catalogue records."""

from dataclasses import dataclass

from app.domain.catalog.loader import Catalog
from app.domain.errors import DomainValidationError
from app.schemas.catalog import CatalogComponent
from app.schemas.mission import SpacecraftArchitecture


class CatalogItemNotFound(DomainValidationError):  # noqa: N818
    def __init__(self, component_id: str, field: str) -> None:
        super().__init__("CATALOG_ITEM_NOT_FOUND", field, f"unknown component {component_id!r}")
        self.component_id = component_id


class CatalogCategoryMismatch(DomainValidationError):  # noqa: N818
    def __init__(self, component_id: str, field: str, expected: str, actual: str) -> None:
        super().__init__(
            "CATALOG_CATEGORY_MISMATCH",
            field,
            f"component {component_id!r} is {actual!r}, expected {expected!r}",
        )


@dataclass(frozen=True)
class ResolvedArchitecture:
    launch: CatalogComponent
    bus: CatalogComponent
    propulsion: CatalogComponent
    power: CatalogComponent
    adcs: CatalogComponent
    communications: CatalogComponent
    thermal: CatalogComponent
    cdh: CatalogComponent
    ground: CatalogComponent
    instruments: tuple[CatalogComponent, ...]

    def all_components(self) -> tuple[CatalogComponent, ...]:
        return (
            self.launch, self.bus, self.propulsion, self.power, self.adcs,
            self.communications, self.thermal, self.cdh, self.ground, *self.instruments,
        )  # fmt: skip


def _fetch(catalog: Catalog, cid: str, category: str, field: str) -> CatalogComponent:
    comp = catalog.get(cid)
    if comp is None:
        raise CatalogItemNotFound(cid, field)
    if comp.category != category:
        raise CatalogCategoryMismatch(cid, field, category, comp.category)
    return comp


def resolve_architecture(arch: SpacecraftArchitecture, catalog: Catalog) -> ResolvedArchitecture:
    return ResolvedArchitecture(
        launch=_fetch(catalog, arch.launch_vehicle_id, "launch", "launchVehicleId"),
        bus=_fetch(catalog, arch.bus_id, "bus", "busId"),
        propulsion=_fetch(catalog, arch.propulsion_id, "propulsion", "propulsionId"),
        power=_fetch(catalog, arch.power_id, "power", "powerId"),
        adcs=_fetch(catalog, arch.adcs_id, "adcs", "adcsId"),
        communications=_fetch(
            catalog, arch.communications_id, "communications", "communicationsId"
        ),
        thermal=_fetch(catalog, arch.thermal_id, "thermal", "thermalId"),
        cdh=_fetch(catalog, arch.cdh_id, "cdh", "cdhId"),
        ground=_fetch(catalog, arch.ground_segment_id, "ground", "groundSegmentId"),
        instruments=tuple(
            _fetch(catalog, cid, "instrument", f"instrumentIds[{i}]")
            for i, cid in enumerate(arch.instrument_ids)
        ),
    )

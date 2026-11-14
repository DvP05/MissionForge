"""Allow-listed uncertain-parameter paths (architecture 19.3, 20).

`UncertainParameter.path` is looked up in ALLOWED_PATHS; it is never evaluated, and no
attribute is fetched by name from a user string. Every path maps to a fixed, typed edit.

Most real-world dispersions (engine Isp, battery capacity, component masses) are catalogue
properties, not MissionState fields, so paths address either the design's *selected*
catalogue components or the operations plan. A sampled value is a multiplier ("scale")
or an additive offset ("offset", in the parameter's own unit).

Physical bounds: a fraction (contact availability, duty cycle) pushed outside [0, 1] is
clamped to the bound and *counted*, so the report states how many draws were clamped.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from app.domain.catalog.loader import Catalog
from app.domain.errors import DomainValidationError
from app.schemas.catalog import CatalogComponent
from app.schemas.mission import MissionState
from app.schemas.units import Quantity


@dataclass(frozen=True)
class PathSpec:
    target: Literal["catalog", "duty-cycle"]
    mode: Literal["scale", "offset"]
    categories: tuple[str, ...]  # catalogue categories ("*" = every selected component)
    parameters: tuple[str, ...]  # catalogue parameter keys
    fraction: bool  # result is a 0..1 fraction (clamped and counted)
    label: str


ALLOWED_PATHS: Mapping[str, PathSpec] = {
    "catalog.propulsion.isp": PathSpec(
        "catalog", "scale", ("propulsion",), ("isp",), False, "Propulsion specific impulse"
    ),
    "catalog.launch.launch_mass_limit": PathSpec(
        "catalog", "scale", ("launch",), ("launch_mass_limit",), False, "Launch delivered mass"
    ),
    "catalog.components.mass": PathSpec(
        "catalog",
        "scale",
        ("*",),
        ("mass", "dry_mass", "structure_mass"),
        False,
        "Component mass growth",
    ),  # fmt: skip
    "catalog.power.array_power_at_1au": PathSpec(
        "catalog", "scale", ("power",), ("array_power_at_1au",), False, "Solar array output"
    ),
    "catalog.power.battery_capacity": PathSpec(
        "catalog", "scale", ("power",), ("battery_capacity",), False, "Battery usable capacity"
    ),
    "catalog.communications.antenna_gain": PathSpec(
        "catalog",
        "offset",
        ("communications",),
        ("antenna_gain",),
        False,
        "Antenna gain / pointing loss",
    ),  # fmt: skip
    "catalog.ground.contact_availability": PathSpec(
        "catalog",
        "scale",
        ("ground",),
        ("contact_availability",),
        True,
        "Ground contact availability",
    ),  # fmt: skip
    "operations.observation_plan.duty_cycle": PathSpec(
        "duty-cycle", "scale", (), (), True, "Instrument duty cycle"
    ),
}


def require_allowed(path: str) -> PathSpec:
    spec = ALLOWED_PATHS.get(path)
    if spec is None:
        raise DomainValidationError(
            "UNCERTAIN_PATH_NOT_ALLOWED", "path", f"path {path!r} is not in the allow-list"
        )
    return spec


def _selected_ids(state: MissionState) -> list[str]:
    a = state.architecture
    ids = [
        a.launch_vehicle_id, a.bus_id, a.propulsion_id, a.power_id, a.adcs_id,
        a.communications_id, a.thermal_id, a.cdh_id, a.ground_segment_id, *a.instrument_ids,
    ]  # fmt: skip
    return list(dict.fromkeys(ids))


def _apply(value: float, spec: PathSpec, x: float) -> tuple[float, bool]:
    out = value * x if spec.mode == "scale" else value + x
    if spec.fraction and not 0.0 <= out <= 1.0:
        return min(1.0, max(0.0, out)), True
    return out, False


@dataclass(frozen=True)
class AppliedSample:
    state: MissionState
    catalog: Catalog
    clamped: int  # how many values hit a physical bound


def apply_samples(
    state: MissionState, catalog: Catalog, values: Mapping[str, float]
) -> AppliedSample:
    """Return a *copy* of state and catalogue with every sampled value applied."""
    for path, x in values.items():
        spec = require_allowed(path)
        if spec.mode == "scale" and x <= 0:
            raise DomainValidationError(
                "INVALID_SAMPLE", path, "a scale factor must be greater than zero"
            )

    clamped = 0
    edited: dict[str, CatalogComponent] = {}
    for cid in _selected_ids(state):
        comp = catalog.get(cid)
        if comp is None:
            continue
        params = dict(comp.parameters)
        changed = False
        for path, x in values.items():
            spec = ALLOWED_PATHS[path]
            if spec.target != "catalog":
                continue
            if "*" not in spec.categories and comp.category not in spec.categories:
                continue
            for key in spec.parameters:
                q = params.get(key)
                if q is None:
                    continue
                new_value, hit = _apply(float(q.value), spec, x)
                clamped += hit
                params[key] = Quantity.model_validate({**q.model_dump(), "value": new_value})
                changed = True
        if changed:
            edited[cid] = comp.model_copy(update={"parameters": params})
    new_catalog = (
        Catalog(catalog.version, tuple(edited.get(c.id, c) for c in catalog.values()))
        if edited
        else catalog
    )

    new_state = state
    duty = [x for p, x in values.items() if ALLOWED_PATHS[p].target == "duty-cycle"]
    if duty:
        spec = ALLOWED_PATHS["operations.observation_plan.duty_cycle"]
        items = []
        for item in state.operations.observation_plan:
            value = float(item.duty_cycle)
            for x in duty:
                value, hit = _apply(value, spec, x)
                clamped += hit
            items.append(item.model_copy(update={"duty_cycle": value}))
        operations = state.operations.model_copy(update={"observation_plan": tuple(items)})
        new_state = state.model_copy(update={"operations": operations})
    return AppliedSample(new_state, new_catalog, clamped)

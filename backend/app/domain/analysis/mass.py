"""Mass budget (architecture §7.1-7.2). Pure, deterministic, SI (kg).

Conventions shared by all analysis modules: a frozen result dataclass carrying
``assumptions``, ``model_id`` and derived ``provenance``; invalid input raises
``DomainValidationError``.

Instrument quantity is the number of times an id appears in
``ResolvedArchitecture.instruments``. Bus ``structure_mass`` is part of bus
``mass`` and is never added again; no generic structure percentage is applied.
"""

from dataclasses import dataclass, field

from app.domain.catalog.resolver import ResolvedArchitecture
from app.domain.errors import DomainValidationError
from app.domain.units.guards import require_finite, require_positive
from app.schemas.catalog import CatalogComponent
from app.schemas.units import Provenance

MODEL_ID = "mass-v1"
COVERAGE_FRACTION = 0.8
PROPELLANT_ID = "propellant"

ASSUMPTIONS: tuple[str, ...] = (
    "Bus structure mass is included in bus mass and is not added separately.",
    "No generic structure/harness percentage is applied; only catalogue masses are summed.",
    "The ground segment contributes no spacecraft mass.",
    "Allocated mass = (dry + propellant) x (1 + margin fraction).",
    "Instrument quantity equals the number of repeated instrument ids.",
)


def _provenance() -> Provenance:
    return Provenance(
        fidelity="derived", source_name="MISSIONFORGE mass model", assumptions=ASSUMPTIONS
    )


@dataclass(frozen=True)
class MassResult:
    payload_kg: float
    subsystem_dry_kg: float
    dry_kg: float
    wet_kg: float
    allocated_kg: float
    margin_to_limit_fraction: float | None
    top_contributors: tuple[tuple[str, float], ...]
    assumptions: tuple[str, ...] = ASSUMPTIONS
    model_id: str = MODEL_ID
    provenance: Provenance = field(default_factory=_provenance)


def _mass(comp: CatalogComponent, key: str) -> float:
    field_name = f"{comp.id}.{key}"
    q = comp.parameters.get(key)
    if q is None:
        raise DomainValidationError("MISSING_PARAMETER", field_name, f"{field_name} is required")
    if q.unit != "kg":
        raise DomainValidationError("WRONG_UNIT", field_name, f"{field_name} must be in kg")
    value = require_finite(q.value, field_name)
    if value < 0.0:
        raise DomainValidationError("NEGATIVE_MASS", field_name, f"{field_name} must be >= 0")
    return value


def compute_mass_budget(
    resolved: ResolvedArchitecture,
    propellant_kg: float,
    margin_fraction: float,
    launch_limit_kg: float | None,
) -> MassResult:
    propellant = require_finite(propellant_kg, "propellant_kg")
    if propellant < 0.0:
        raise DomainValidationError("NEGATIVE_MASS", "propellant_kg", "propellant_kg must be >= 0")
    margin = require_finite(margin_fraction, "margin_fraction")
    if margin < 0.0:
        raise DomainValidationError(
            "NEGATIVE_MARGIN", "margin_fraction", "margin_fraction must be >= 0"
        )
    limit = (
        None if launch_limit_kg is None else require_positive(launch_limit_kg, "launch_limit_kg")
    )

    contrib: dict[str, float] = {}

    def add(comp: CatalogComponent, key: str) -> float:
        m = _mass(comp, key)
        contrib[comp.id] = contrib.get(comp.id, 0.0) + m
        return m

    subsystem_dry = (
        add(resolved.bus, "mass")  # includes structure_mass
        + add(resolved.propulsion, "dry_mass")
        + add(resolved.power, "mass")
        + add(resolved.adcs, "mass")
        + add(resolved.communications, "mass")
        + add(resolved.thermal, "mass")
        + add(resolved.cdh, "mass")
    )
    payload = sum((add(i, "mass") for i in resolved.instruments), 0.0)
    dry = payload + subsystem_dry
    wet = dry + propellant
    allocated = wet * (1.0 + margin)
    margin_to_limit = None if limit is None else (limit - allocated) / limit

    contrib[PROPELLANT_ID] = contrib.get(PROPELLANT_ID, 0.0) + propellant
    ordered = sorted(contrib.items(), key=lambda kv: (-kv[1], kv[0]))
    target = COVERAGE_FRACTION * wet
    top: list[tuple[str, float]] = []
    cumulative = 0.0
    for cid, kg in ordered:
        if cumulative >= target:
            break
        top.append((cid, kg))
        cumulative += kg

    return MassResult(
        payload_kg=payload,
        subsystem_dry_kg=subsystem_dry,
        dry_kg=dry,
        wet_kg=wet,
        allocated_kg=allocated,
        margin_to_limit_fraction=margin_to_limit,
        top_contributors=tuple(top),
    )

"""Propulsion / delta-v (architecture §7.3). Pure, deterministic, SI.

Tsiolkovsky rocket equation with physical masses (R13): m0 = dry + propellant,
mf = dry. Only ``source == "spacecraft"`` maneuvers count toward the required
delta-v; ``trajectory-info`` items (e.g. JPL ``dv_tot``/C3 figures) are
returned separately and never summed.
"""

import math
from dataclasses import dataclass, field
from typing import Literal

from app.domain.analysis._params import derived_provenance, param_value
from app.domain.errors import DomainValidationError
from app.domain.units.constants import G0
from app.domain.units.guards import require_finite, require_positive
from app.schemas.catalog import CatalogComponent
from app.schemas.units import Provenance

MODEL_ID = "propulsion-v1"
LOW_THRUST_WARNING = "low-thrust propulsion: long burn durations not modelled (Tier 3)"

ASSUMPTIONS: tuple[str, ...] = (
    "Delta-v = Isp x g0 x ln(m0/mf) with physical masses (m0 = dry + propellant, mf = dry).",
    "Only spacecraft maneuvers count toward required delta-v; trajectory-info items are "
    "informational and never summed.",
    "Impulsive maneuvers; gravity, drag and steering losses are not modelled.",
    "Margin = available - required - reserve.",
)

# Resolver exposes the propulsion component as a CatalogComponent.
ResolvedPropulsion = CatalogComponent


def _provenance(assumptions: tuple[str, ...]) -> Provenance:
    return derived_provenance("MISSIONFORGE propulsion model", assumptions)


@dataclass(frozen=True)
class Maneuver:
    id: str
    dv_ms: float
    source: Literal["spacecraft", "trajectory-info"]


@dataclass(frozen=True)
class ManeuverBudget:
    available_ms: float
    required_ms: float
    margin_ms: float
    per_maneuver: tuple[tuple[str, float], ...]  # cumulative dv after each spacecraft maneuver
    reserve_consumed_by: str | None
    informational: tuple[Maneuver, ...]
    assumptions: tuple[str, ...] = ASSUMPTIONS
    model_id: str = MODEL_ID
    provenance: Provenance = field(default_factory=lambda: _provenance(ASSUMPTIONS))


def delta_v_ms(isp_s: float, m0_kg: float, mf_kg: float) -> float:
    isp = require_positive(isp_s, "isp_s")
    mf = require_positive(mf_kg, "mf_kg")
    m0 = require_finite(m0_kg, "m0_kg")
    if m0 <= mf:
        raise DomainValidationError("INVALID_MASS_RATIO", "m0_kg", "m0_kg must exceed mf_kg")
    return isp * G0 * math.log(m0 / mf)


def propellant_for_delta_v(isp_s: float, mf_kg: float, dv_ms: float) -> float:
    isp = require_positive(isp_s, "isp_s")
    mf = require_positive(mf_kg, "mf_kg")
    dv = require_positive(dv_ms, "dv_ms")
    return mf * math.expm1(dv / (isp * G0))


def _param(comp: CatalogComponent, key: str, unit: str) -> float:
    return param_value(comp, key, unit, field=f"{comp.id}.{key}")


def maneuver_budget(
    prop: ResolvedPropulsion,
    dry_kg: float,
    required: list[Maneuver],
    reserve_ms: float,
    *,
    propellant_kg: float,
) -> ManeuverBudget:
    isp = require_positive(_param(prop, "isp", "s"), f"{prop.id}.isp")
    capacity = _param(prop, "propellant_capacity", "kg")
    dry = require_positive(dry_kg, "dry_kg")
    reserve = require_finite(reserve_ms, "reserve_ms")
    if reserve < 0.0:
        raise DomainValidationError("NEGATIVE_RESERVE", "reserve_ms", "reserve_ms must be >= 0")
    loaded = require_finite(propellant_kg, "propellant_kg")
    if loaded < 0.0:
        raise DomainValidationError("NEGATIVE_MASS", "propellant_kg", "propellant_kg must be >= 0")
    if loaded > capacity:
        raise DomainValidationError(
            "PROPELLANT_EXCEEDS_CAPACITY",
            "propellant_kg",
            f"propellant_kg {loaded} exceeds capacity {capacity}",
        )

    available = delta_v_ms(isp, dry + loaded, dry) if loaded > 0.0 else 0.0

    counted: list[Maneuver] = []
    info: list[Maneuver] = []
    for i, m in enumerate(required):
        field_name = f"required[{i}]"
        require_finite(m.dv_ms, f"{field_name}.dv_ms")
        if m.dv_ms < 0.0:
            raise DomainValidationError(
                "NEGATIVE_DELTA_V", f"{field_name}.dv_ms", "dv_ms must be >= 0"
            )
        if m.source == "spacecraft":
            counted.append(m)
        elif m.source == "trajectory-info":
            info.append(m)
        else:
            raise DomainValidationError(
                "INVALID_SOURCE", f"{field_name}.source", f"unknown maneuver source {m.source!r}"
            )

    usable = available - reserve
    cumulative = 0.0
    per: list[tuple[str, float]] = []
    consumer: str | None = None
    for m in counted:
        cumulative += m.dv_ms
        per.append((m.id, cumulative))
        if consumer is None and cumulative > usable:
            consumer = m.id

    assumptions = ASSUMPTIONS
    if "low-thrust" in prop.tags:
        assumptions = (*ASSUMPTIONS, LOW_THRUST_WARNING)
    return ManeuverBudget(
        available_ms=available,
        required_ms=cumulative,
        margin_ms=available - cumulative - reserve,
        per_maneuver=tuple(per),
        reserve_consumed_by=consumer,
        informational=tuple(info),
        assumptions=assumptions,
        provenance=_provenance(assumptions),
    )

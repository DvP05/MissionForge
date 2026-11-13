"""Cost estimate (architecture §7.8). Pure, USD. Every figure is a gameplay estimate.

Catalogue costs are illustrative (R3). Ground ``cost`` is per mission-year, so it is
scaled by ``ops_days / 365.25``. Instrument repeats are counted once per repeat.
"""

from dataclasses import dataclass, field

from app.domain.analysis._params import param_value
from app.domain.catalog.resolver import ResolvedArchitecture
from app.domain.errors import DomainValidationError
from app.domain.units.guards import require_finite
from app.schemas.catalog import CatalogComponent
from app.schemas.units import Provenance

MODEL_ID = "cost-v1"
DAYS_PER_YEAR = 365.25

ASSUMPTIONS: tuple[str, ...] = (
    "All costs are illustrative gameplay estimates, not real prices.",
    "Hardware = sum of spacecraft component costs; instrument repeats are counted.",
    "Launch cost = launch-vehicle component cost.",
    "Ground cost = ground-segment cost per mission-year x ops_days / 365.25.",
    "Operations = ops_cost_per_day x ops_days.",
    "Development = development_fraction x hardware.",
    "Reserves = reserve_fraction x (hardware + launch + operations + ground + development).",
    "Low/high bounds are total x low_factor / high_factor (not a statistical interval).",
)


def _provenance() -> Provenance:
    return Provenance(
        fidelity="gameplay-estimate",
        source_name="MISSIONFORGE cost model",
        assumptions=ASSUMPTIONS,
    )


@dataclass(frozen=True)
class CostParams:
    ops_cost_per_day_usd: float = 5_000.0
    development_fraction: float = 0.3
    reserve_fraction: float = 0.2
    low_factor: float = 0.8
    high_factor: float = 1.4

    def __post_init__(self) -> None:
        for name in ("ops_cost_per_day_usd", "development_fraction", "reserve_fraction"):
            if require_finite(getattr(self, name), name) < 0.0:
                raise DomainValidationError("NEGATIVE_COST_PARAM", name, f"{name} must be >= 0")
        if not 0.0 < require_finite(self.low_factor, "low_factor") <= 1.0:
            raise DomainValidationError("INVALID_LOW_FACTOR", "low_factor", "must be in (0, 1]")
        if require_finite(self.high_factor, "high_factor") < 1.0:
            raise DomainValidationError("INVALID_HIGH_FACTOR", "high_factor", "must be >= 1")


@dataclass(frozen=True)
class CostBreakdown:
    hardware: float
    launch: float
    operations: float
    ground: float
    reserves: float
    development: float
    total: float
    low: float
    high: float
    assumptions: tuple[str, ...] = ASSUMPTIONS
    model_id: str = MODEL_ID
    provenance: Provenance = field(default_factory=_provenance)


def _cost(comp: CatalogComponent) -> float:
    name = f"{comp.id}.cost"
    value = param_value(comp, "cost", "USD", field=name)
    if value < 0.0:
        raise DomainValidationError("NEGATIVE_COST", name, f"{name} must be >= 0")
    return value


def cost_estimate(
    resolved: ResolvedArchitecture, ops_days: float, params: CostParams
) -> CostBreakdown:
    days = require_finite(ops_days, "ops_days")
    if days < 0.0:
        raise DomainValidationError("NEGATIVE_DURATION", "ops_days", "ops_days must be >= 0")
    spacecraft = (
        resolved.bus, resolved.propulsion, resolved.power, resolved.adcs,
        resolved.communications, resolved.thermal, resolved.cdh, *resolved.instruments,
    )  # fmt: skip
    hardware = sum((_cost(c) for c in spacecraft), 0.0)
    launch = _cost(resolved.launch)
    operations = params.ops_cost_per_day_usd * days
    ground = _cost(resolved.ground) * days / DAYS_PER_YEAR
    development = params.development_fraction * hardware
    subtotal = hardware + launch + operations + ground + development
    reserves = params.reserve_fraction * subtotal
    total = subtotal + reserves
    return CostBreakdown(
        hardware=hardware,
        launch=launch,
        operations=operations,
        ground=ground,
        reserves=reserves,
        development=development,
        total=total,
        low=total * params.low_factor,
        high=total * params.high_factor,
    )

"""Power & energy (architecture section 7.4). Pure, deterministic.

Units: power in W, energy in Wh at the API surface. Seconds are converted to
energy explicitly via ``app.domain.units.conversions.j_to_wh`` (W x s = J).
W and Wh are never mixed: catalogue parameters are read with their expected
unit and a mismatch raises ``WRONG_UNIT``.
"""

import math
from dataclasses import dataclass, field

from app.domain.analysis._params import derived_provenance, param_value
from app.domain.errors import DomainValidationError
from app.domain.units.constants import SOLAR_CONSTANT_W_M2
from app.domain.units.conversions import j_to_wh
from app.domain.units.guards import require_finite, require_fraction, require_positive
from app.schemas.catalog import CatalogComponent
from app.schemas.units import Provenance

MODEL_ID = "power-v1"

ASSUMPTIONS: tuple[str, ...] = (
    "Solar flux = 1 AU solar constant / d^2 (gameplay-estimate constant, inverse-square only).",
    "Array generation = P_1AU / d^2 x EPS efficiency x cos(incidence); incidence beyond "
    "90 degrees gives zero generation. No degradation, temperature or shadowing effects.",
    "Average power = sum(P x duty); peak power = sum of P for every load with duty > 0, "
    "assuming all such loads run simultaneously (worst case).",
    "Battery starts full. Surplus charges the battery up to capacity with no charge "
    "efficiency loss; deficits draw deficit / discharge_efficiency from the battery.",
    "State of charge floor = 1 - usable DoD; the ledger closes only if SOC never drops below it.",
    "Power is constant within each phase, so SOC extremes occur at phase boundaries.",
)


def _provenance() -> Provenance:
    return derived_provenance("MISSIONFORGE power model", ASSUMPTIONS)


@dataclass(frozen=True)
class Load:
    id: str
    power_w: float
    duty_cycle: float  # fraction 0..1


@dataclass(frozen=True)
class PowerPhase:
    id: str
    duration_s: float
    generation_w: float
    loads: tuple[Load, ...]


@dataclass(frozen=True)
class Battery:
    capacity_wh: float
    usable_dod: float  # fraction
    discharge_efficiency: float  # fraction


@dataclass(frozen=True)
class PhaseEnergy:
    id: str
    duration_s: float
    generation_wh: float
    consumption_wh: float
    start_wh: float
    end_wh: float
    soc_end_fraction: float
    unmet_wh: float  # demand the battery could not supply (clamped at empty)


@dataclass(frozen=True)
class EnergyLedger:
    per_phase: tuple[PhaseEnergy, ...]
    min_soc_fraction: float
    soc_floor_fraction: float
    closes: bool
    assumptions: tuple[str, ...] = ASSUMPTIONS
    model_id: str = MODEL_ID
    provenance: Provenance = field(default_factory=_provenance)


@dataclass(frozen=True)
class PowerCheck:
    avg_ok: bool
    peak_ok: bool
    avg_margin_w: float  # supply - avg x (1 + margin)
    peak_margin_w: float  # supply - peak x (1 + margin)


@dataclass(frozen=True)
class SolarArrayParams:
    array_power_at_1au_w: float
    eps_efficiency: float


def _check_load(load: Load, idx: int) -> tuple[float, float]:
    name = f"loads[{idx}].power_w"
    p = require_finite(load.power_w, name)
    if p < 0.0:
        raise DomainValidationError("NEGATIVE_POWER", name, f"{name} must be >= 0")
    d = require_fraction(load.duty_cycle, f"loads[{idx}].duty_cycle")
    return p, d


def average_power_w(loads: list[Load]) -> float:
    total = 0.0
    for i, load in enumerate(loads):
        p, d = _check_load(load, i)
        total += p * d
    return total


def peak_power_w(loads: list[Load]) -> float:
    total = 0.0
    for i, load in enumerate(loads):
        p, d = _check_load(load, i)
        if d > 0.0:
            total += p
    return total


def solar_flux_at(distance_au: float) -> float:
    d = require_positive(distance_au, "distance_au")
    return SOLAR_CONSTANT_W_M2 / (d * d)


def _cos_incidence(incidence_rad: float) -> float:
    inc = require_finite(incidence_rad, "incidence_rad")
    return max(0.0, math.cos(inc))


def solar_generation_w(
    flux_w_m2: float, area_m2: float, cell_eff: float, eps_eff: float, incidence_rad: float
) -> float:
    flux = require_finite(flux_w_m2, "flux_w_m2")
    area = require_finite(area_m2, "area_m2")
    if flux < 0.0 or area < 0.0:
        raise DomainValidationError("NEGATIVE_VALUE", "flux_w_m2", "flux and area must be >= 0")
    cell = require_fraction(cell_eff, "cell_eff")
    eps = require_fraction(eps_eff, "eps_eff")
    return flux * area * cell * eps * _cos_incidence(incidence_rad)


def array_generation_w(
    array_power_at_1au_w: float, distance_au: float, eps_eff: float, incidence_rad: float
) -> float:
    p1 = require_finite(array_power_at_1au_w, "array_power_at_1au_w")
    if p1 < 0.0:
        raise DomainValidationError("NEGATIVE_POWER", "array_power_at_1au_w", "must be >= 0")
    d = require_positive(distance_au, "distance_au")
    eps = require_fraction(eps_eff, "eps_eff")
    return p1 / (d * d) * eps * _cos_incidence(incidence_rad)


def eclipse_battery_required_wh(
    eclipse_power_w: float, eclipse_s: float, usable_dod: float, discharge_eff: float
) -> float:
    p = require_finite(eclipse_power_w, "eclipse_power_w")
    t = require_finite(eclipse_s, "eclipse_s")
    if p < 0.0 or t < 0.0:
        raise DomainValidationError("NEGATIVE_VALUE", "eclipse_power_w", "power and time >= 0")
    dod = require_positive(usable_dod, "usable_dod")
    eff = require_positive(discharge_eff, "discharge_eff")
    if dod > 1.0 or eff > 1.0:
        raise DomainValidationError("NOT_A_FRACTION", "usable_dod", "must be within (0, 1]")
    return j_to_wh(p * t) / (dod * eff)


def power_check(avg_w: float, peak_w: float, supply_w: float, margin_fraction: float) -> PowerCheck:
    avg = require_finite(avg_w, "avg_w")
    peak = require_finite(peak_w, "peak_w")
    supply = require_finite(supply_w, "supply_w")
    margin = require_finite(margin_fraction, "margin_fraction")
    if margin < 0.0:
        raise DomainValidationError(
            "NEGATIVE_MARGIN", "margin_fraction", "margin_fraction must be >= 0"
        )
    avg_margin = supply - avg * (1.0 + margin)
    peak_margin = supply - peak * (1.0 + margin)
    return PowerCheck(
        avg_ok=avg_margin >= 0.0,
        peak_ok=peak_margin >= 0.0,
        avg_margin_w=avg_margin,
        peak_margin_w=peak_margin,
    )


def solar_array_params(power: CatalogComponent) -> SolarArrayParams:
    return SolarArrayParams(
        array_power_at_1au_w=param_value(
            power, "array_power_at_1au", "W", field=f"{power.id}.array_power_at_1au"
        ),
        eps_efficiency=param_value(
            power, "eps_efficiency", "fraction", field=f"{power.id}.eps_efficiency"
        ),
    )


def battery_from_component(power: CatalogComponent, *, discharge_efficiency: float) -> Battery:
    return Battery(
        capacity_wh=param_value(
            power, "battery_capacity", "Wh", field=f"{power.id}.battery_capacity"
        ),
        usable_dod=param_value(power, "usable_dod", "fraction", field=f"{power.id}.usable_dod"),
        discharge_efficiency=discharge_efficiency,
    )


def energy_ledger(phases: list[PowerPhase], battery: Battery) -> EnergyLedger:
    cap = require_positive(battery.capacity_wh, "battery.capacity_wh")
    dod = require_positive(battery.usable_dod, "battery.usable_dod")
    eff = require_positive(battery.discharge_efficiency, "battery.discharge_efficiency")
    if dod > 1.0 or eff > 1.0:
        raise DomainValidationError(
            "NOT_A_FRACTION", "battery", "usable_dod and discharge_efficiency must be <= 1"
        )
    floor = 1.0 - dod

    level = cap
    min_soc = 1.0
    out: list[PhaseEnergy] = []
    for i, ph in enumerate(phases):
        dur = require_finite(ph.duration_s, f"phases[{i}].duration_s")
        if dur < 0.0:
            raise DomainValidationError(
                "NEGATIVE_DURATION", f"phases[{i}].duration_s", "duration_s must be >= 0"
            )
        gen_w = require_finite(ph.generation_w, f"phases[{i}].generation_w")
        if gen_w < 0.0:
            raise DomainValidationError(
                "NEGATIVE_POWER", f"phases[{i}].generation_w", "generation_w must be >= 0"
            )
        gen_wh = j_to_wh(gen_w * dur)
        cons_wh = j_to_wh(average_power_w(list(ph.loads)) * dur)
        start = level
        net = gen_wh - cons_wh
        unmet = 0.0
        if net >= 0.0:
            level = min(cap, start + net)
        else:
            draw = -net / eff
            if draw > start:
                unmet = (draw - start) * eff
                level = 0.0
            else:
                level = start - draw
        soc = level / cap
        min_soc = min(min_soc, soc)
        out.append(PhaseEnergy(ph.id, dur, gen_wh, cons_wh, start, level, soc, unmet))

    return EnergyLedger(
        per_phase=tuple(out),
        min_soc_fraction=min_soc,
        soc_floor_fraction=floor,
        closes=min_soc >= floor - 1e-12,
    )

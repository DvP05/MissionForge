"""RF link budget (architecture section 7.5). Pure, deterministic.

Units: power W, gains dBi, losses dB, frequency Hz, range m, temperature K,
bit rate bit/s. Equation convention (matches the template-test helper exactly):
implementation loss is an explicit loss term inside Pr, so
``margin = Eb/N0 - required_Eb/N0`` where Eb/N0 already includes it.
This is a simplified teaching model, not a DSN-compatible design certification.
"""

import math
from dataclasses import dataclass, field

from app.domain.analysis._params import derived_provenance, param_value
from app.domain.errors import DomainValidationError
from app.domain.units.constants import KB, C
from app.domain.units.conversions import w_to_dbw
from app.domain.units.guards import require_finite, require_positive
from app.schemas.catalog import CatalogComponent
from app.schemas.units import Provenance

MODEL_ID = "comms-v1"

ASSUMPTIONS: tuple[str, ...] = (
    "Free-space path loss only: FSPL = 20 log10(4 pi d / lambda); no atmosphere, pointing or "
    "polarisation loss beyond the explicit losses supplied.",
    "Pr = Pt + Gt + Gr - FSPL - implementation loss - other losses (implementation loss is an "
    "explicit loss term); margin = Eb/N0 - required Eb/N0.",
    "Noise N0 = kB x system noise temperature; no interference or coding-gain modelling.",
    "capacity_bps is the highest bit rate with margin >= 0 (not capped by hardware).",
)


def _provenance() -> Provenance:
    return derived_provenance("MISSIONFORGE comms model", ASSUMPTIONS)


@dataclass(frozen=True)
class LinkInput:
    tx_power_w: float
    tx_gain_dbi: float
    rx_gain_dbi: float
    frequency_hz: float
    range_m: float
    system_noise_temp_k: float
    bit_rate_bps: float
    required_ebn0_db: float
    implementation_loss_db: float
    other_losses_db: float = 0.0


@dataclass(frozen=True)
class LinkResult:
    fspl_db: float
    eirp_dbw: float
    pr_dbw: float
    n0_dbw_per_hz: float
    cn0_dbhz: float
    ebn0_db: float
    margin_db: float
    capacity_bps: float
    assumptions: tuple[str, ...] = ASSUMPTIONS
    model_id: str = MODEL_ID
    provenance: Provenance = field(default_factory=_provenance)


def fspl_db(range_m: float, freq_hz: float) -> float:
    d = require_positive(range_m, "range_m")
    f = require_positive(freq_hz, "freq_hz")
    return 20.0 * math.log10(4.0 * math.pi * d * f / C)


def link_budget(inp: LinkInput) -> LinkResult:
    p_w = require_positive(inp.tx_power_w, "tx_power_w")
    gt = require_finite(inp.tx_gain_dbi, "tx_gain_dbi")
    gr = require_finite(inp.rx_gain_dbi, "rx_gain_dbi")
    t_sys = require_positive(inp.system_noise_temp_k, "system_noise_temp_k")
    rate = require_positive(inp.bit_rate_bps, "bit_rate_bps")
    req = require_finite(inp.required_ebn0_db, "required_ebn0_db")
    impl = require_finite(inp.implementation_loss_db, "implementation_loss_db")
    other = require_finite(inp.other_losses_db, "other_losses_db")
    for name, v in (("implementation_loss_db", impl), ("other_losses_db", other)):
        if v < 0.0:
            raise DomainValidationError("NEGATIVE_LOSS", name, f"{name} must be >= 0")

    loss = fspl_db(inp.range_m, inp.frequency_hz)
    eirp = w_to_dbw(p_w) + gt
    pr = eirp + gr - loss - impl - other
    n0 = 10.0 * math.log10(KB * t_sys)
    cn0 = pr - n0
    ebn0 = cn0 - 10.0 * math.log10(rate)
    return LinkResult(
        fspl_db=loss,
        eirp_dbw=eirp,
        pr_dbw=pr,
        n0_dbw_per_hz=n0,
        cn0_dbhz=cn0,
        ebn0_db=ebn0,
        margin_db=ebn0 - req,
        capacity_bps=10.0 ** ((cn0 - req) / 10.0),
    )


def link_input_from_components(
    comms: CatalogComponent, ground: CatalogComponent, *, range_m: float, bit_rate_bps: float
) -> LinkInput:
    def cp(key: str, unit: str) -> float:
        return param_value(comms, key, unit, field=f"{comms.id}.{key}")

    return LinkInput(
        tx_power_w=cp("tx_power", "W"),
        tx_gain_dbi=cp("antenna_gain", "dB"),
        rx_gain_dbi=param_value(ground, "station_gain", "dB", field=f"{ground.id}.station_gain"),
        frequency_hz=cp("frequency", "Hz"),
        range_m=range_m,
        system_noise_temp_k=param_value(
            ground, "noise_temperature", "K", field=f"{ground.id}.noise_temperature"
        ),
        bit_rate_bps=bit_rate_bps,
        required_ebn0_db=cp("required_ebn0", "dB"),
        implementation_loss_db=cp("implementation_loss", "dB"),
    )

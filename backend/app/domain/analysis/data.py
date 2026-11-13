"""Onboard data ledger (architecture section 7.5). Pure, deterministic.

Units: bits, seconds, bit/s. Time is split into piecewise-constant segments at every
observation/contact boundary; within a segment generation and downlink run concurrently,
so a contact only ever sees bits generated up to the current time.
"""

from dataclasses import dataclass, field

from app.domain.analysis._params import derived_provenance, param_value
from app.domain.analysis.comms import link_budget, link_input_from_components
from app.domain.errors import DomainValidationError
from app.domain.units.conversions import day_to_s
from app.domain.units.guards import require_finite, require_fraction, require_positive
from app.schemas.catalog import CatalogComponent
from app.schemas.mission import DownlinkPlanItem, ObservationPlanItem
from app.schemas.units import Provenance

MODEL_ID = "data-v1"

# gameplay-estimate: fraction of contact time carrying payload data after framing/protocol
# overhead (architecture 7.5 protocolEfficiency, R13). Not a measured value.
PROTOCOL_EFFICIENCY = 0.9

ASSUMPTIONS: tuple[str, ...] = (
    "PROTOCOL_EFFICIENCY = 0.9 is a gameplay-estimate constant (R13).",
    "Contact rate = min(planned, comms max_data_rate) if link margin at that rate >= 0, else 0.",
    "Contact bits = rate x duration x protocol efficiency x ground availability, never more "
    "than the bits available (buffered plus generated so far) at that moment.",
    "Observations generate uniformly over their window (rate x duty x compression); "
    "generation and downlink proceed concurrently where windows overlap.",
    "Buffer clamps at capacity; excess is lost and reported as overflow_bits.",
    "margin_fraction = (downlinked - generated) / generated; 0 when nothing is generated.",
)


def _provenance() -> Provenance:
    return derived_provenance("MISSIONFORGE data model", ASSUMPTIONS)


@dataclass(frozen=True)
class ObservationEvent:
    start_s: float
    duration_s: float
    data_rate_bps: float
    duty_cycle: float


@dataclass(frozen=True)
class ContactEvent:
    start_s: float
    duration_s: float
    planned_rate_bps: float
    max_rate_bps: float
    link_margin_db: float  # margin at min(planned, max) rate
    availability_fraction: float


@dataclass(frozen=True)
class ContactResult:
    start_s: float
    rate_bps: float  # achievable rate (0 if the link does not close)
    capacity_bits: float  # rate x duration x efficiency x availability
    downlinked_bits: float  # capacity limited by buffer contents


@dataclass(frozen=True)
class DataLedger:
    generated_bits: float
    downlinked_bits: float
    buffer_timeline: tuple[tuple[float, float], ...]  # (t_s, buffered bits) after each event
    peak_buffer_bits: float
    overflow_bits: float
    margin_fraction: float
    per_contact: tuple[ContactResult, ...]
    end_buffer_bits: float = 0.0
    assumptions: tuple[str, ...] = ASSUMPTIONS
    model_id: str = MODEL_ID
    provenance: Provenance = field(default_factory=_provenance)


def _nonneg(x: float, name: str) -> float:
    v = require_finite(x, name)
    if v < 0.0:
        raise DomainValidationError("NEGATIVE_VALUE", name, f"{name} must be >= 0")
    return v


def contact_rate_bps(planned_bps: float, max_bps: float, link_margin_db: float) -> float:
    planned = require_positive(planned_bps, "planned_rate_bps")
    cap = require_positive(max_bps, "max_rate_bps")
    margin = require_finite(link_margin_db, "link_margin_db")
    return min(planned, cap) if margin >= 0.0 else 0.0


def data_ledger(
    observations: list[ObservationEvent],
    contacts: list[ContactEvent],
    buffer_capacity_bits: float,
    protocol_eff: float = PROTOCOL_EFFICIENCY,
    compression: float = 1.0,
) -> DataLedger:
    cap = require_positive(buffer_capacity_bits, "buffer_capacity_bits")
    eff = require_fraction(protocol_eff, "protocol_eff")
    comp = require_positive(compression, "compression")

    # (start, end, generation bit/s)
    obs_w: list[tuple[float, float, float]] = []
    generated = 0.0
    for i, o in enumerate(observations):
        start = _nonneg(o.start_s, f"observations[{i}].start_s")
        dur = _nonneg(o.duration_s, f"observations[{i}].duration_s")
        g = (
            _nonneg(o.data_rate_bps, f"observations[{i}].data_rate_bps")
            * require_fraction(o.duty_cycle, f"observations[{i}].duty_cycle")
            * comp
        )
        obs_w.append((start, start + dur, g))
        generated += g * dur

    # (start, end, downlink bit/s)
    con_w: list[tuple[float, float, float]] = []
    rates: list[float] = []
    capacities: list[float] = []
    for i, c in enumerate(contacts):
        start = _nonneg(c.start_s, f"contacts[{i}].start_s")
        dur = _nonneg(c.duration_s, f"contacts[{i}].duration_s")
        rate = contact_rate_bps(c.planned_rate_bps, c.max_rate_bps, c.link_margin_db)
        avail = require_fraction(c.availability_fraction, f"contacts[{i}].availability_fraction")
        eff_rate = rate * eff * avail
        con_w.append((start, start + dur, eff_rate))
        rates.append(rate)
        capacities.append(eff_rate * dur)

    times = sorted({t for w in (*obs_w, *con_w) for t in w[:2]})
    sent_by = [0.0] * len(contacts)
    buf = downlinked = overflow = peak = 0.0
    timeline: list[tuple[float, float]] = [(times[0], 0.0)] if times else []
    for t0, t1 in zip(times, times[1:], strict=False):
        dt = t1 - t0
        gen = sum(g for s0, e0, g in obs_w if s0 <= t0 and t1 <= e0)
        active = [(i, d) for i, (s0, e0, d) in enumerate(con_w) if s0 <= t0 and t1 <= e0]
        drain = sum(d for _, d in active)
        wanted = drain * dt
        sent = min(wanted, buf + gen * dt)  # cannot send bits that do not exist yet
        new = buf + gen * dt - sent
        stored = min(new, cap)
        overflow += new - stored
        buf = stored
        downlinked += sent
        if wanted > 0.0:
            for i, d in active:
                sent_by[i] += sent * d / drain
        peak = max(peak, buf)
        timeline.append((t1, buf))

    results = tuple(
        ContactResult(con_w[i][0], rates[i], capacities[i], sent_by[i])
        for i in sorted(range(len(contacts)), key=lambda k: con_w[k][0])
    )
    return DataLedger(
        generated_bits=generated,
        downlinked_bits=downlinked,
        buffer_timeline=tuple(timeline),
        peak_buffer_bits=peak,
        overflow_bits=overflow,
        margin_fraction=(downlinked - generated) / generated if generated > 0.0 else 0.0,
        per_contact=results,
        end_buffer_bits=buf,
    )


def observation_events_from_plan(
    plan: tuple[ObservationPlanItem, ...], data_rate_bps_by_measurement: dict[str, float]
) -> list[ObservationEvent]:
    out: list[ObservationEvent] = []
    for item in plan:
        rate = data_rate_bps_by_measurement.get(item.measurement_id)
        if rate is None:
            raise DomainValidationError(
                "UNKNOWN_MEASUREMENT",
                item.measurement_id,
                f"no instrument data rate for measurement {item.measurement_id}",
            )
        out.append(
            ObservationEvent(
                start_s=day_to_s(item.start_day),
                duration_s=item.duration_hours * 3600.0,
                data_rate_bps=rate,
                duty_cycle=item.duty_cycle,
            )
        )
    return out


def contact_events_from_plan(
    plan: tuple[DownlinkPlanItem, ...],
    comms: CatalogComponent,
    ground: CatalogComponent,
    *,
    range_m: float,
) -> list[ContactEvent]:
    max_rate = param_value(comms, "max_data_rate", "bit/s", field=f"{comms.id}.max_data_rate")
    avail = param_value(
        ground, "contact_availability", "fraction", field=f"{ground.id}.contact_availability"
    )
    out: list[ContactEvent] = []
    for item in plan:
        rate = min(item.data_rate_bits_per_second, max_rate)
        link = link_input_from_components(comms, ground, range_m=range_m, bit_rate_bps=rate)
        out.append(
            ContactEvent(
                start_s=day_to_s(item.start_day),
                duration_s=item.duration_minutes * 60.0,
                planned_rate_bps=item.data_rate_bits_per_second,
                max_rate_bps=max_rate,
                link_margin_db=link_budget(link).margin_db,
                availability_fraction=avail,
            )
        )
    return out

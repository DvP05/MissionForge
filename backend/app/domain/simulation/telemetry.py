"""Telemetry checkpoints read from the engineering analysis (architecture 9.3, M14).

Checkpoints: every phase transition, the rendezvous burn, every observation start and every
contact start. Each checkpoint carries ``battery_soc``, ``propellant_fraction``,
``buffer_fill`` and ``pointing_error_deg``; contact checkpoints add ``link_margin_db``.
Values come from the AnalysisContext the analysis was computed from (no engineering
formula is re-implemented):

* ``battery_soc`` (fraction, derived): end-of-cycle state of charge of the analysis power
  ledger's representative cycle -- the science cycle during science-ops, the cruise cycle
  otherwise (worst sunlit/eclipse part). Day 0 is a full battery (gameplay-estimate).
* ``propellant_fraction`` (fraction, derived): loaded propellant remaining after the
  cumulative spacecraft delta-v, from the rocket equation inverted on the analysis masses:
  with ``R = (dry + propellant) / dry`` and available delta-v ``dV_a``,
  ``remaining = (R ** (1 - dV / dV_a) - 1) / (R - 1)``. Spacecraft maneuvers are flown at
  arrival.
* ``buffer_fill`` (fraction, derived): data-ledger buffer contents at the checkpoint (last
  ledger step at or before it) / C&DH storage.
* ``link_margin_db`` (dB, derived): link margin of that contact at the reference Earth range
  and the capped contact rate (R19). Not reported outside contacts.
* ``pointing_error_deg`` (deg, gameplay-estimate): proxy = ADCS pointing accuracy from the
  catalogue; attitude dynamics are not modelled.

Event effects (Task 4.2, ``TelemetryOverlay``): every anomaly / scenario event day adds an
``event`` checkpoint; ``soc_delta`` dips the battery at that checkpoint only (it recovers by
the next one, gameplay-estimate); ``propellant_delta`` steps apply from their day on; buffer
losses are subtracted from the buffer from their day on (clamped at 0); after a termination
no checkpoint is taken except a final one in phase ``terminated``.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from app.domain.analysis.context import AnalysisContext
from app.domain.simulation.phases import PhaseSchedule
from app.domain.units.conversions import day_to_s
from app.schemas.mission import MissionState
from app.schemas.simulation import Phase, TelemetrySample
from app.schemas.units import Fidelity, Unit

TELEMETRY_CHANNELS: tuple[str, ...] = (
    "battery_soc",
    "propellant_fraction",
    "buffer_fill",
    "link_margin_db",
    "pointing_error_deg",
)
TELEMETRY_UNITS: dict[str, Unit] = {
    "battery_soc": "fraction",
    "propellant_fraction": "fraction",
    "buffer_fill": "fraction",
    "link_margin_db": "dB",
    "pointing_error_deg": "deg",
}
TELEMETRY_ASSUMPTIONS: tuple[str, ...] = (
    "Telemetry is sampled at phase, maneuver, observation and contact checkpoints from the "
    "engineering analysis; it is not a time-stepped subsystem simulation.",
    "Battery state of charge is the end-of-cycle value of the analysis representative power "
    "cycle for the phase; the battery is full at launch (gameplay-estimate).",
    "Pointing error is a proxy equal to the ADCS pointing accuracy (gameplay-estimate).",
    "Link margin is reported at contacts only, at the scenario reference Earth range.",
)


def _clamp01(x: float) -> float:
    return min(1.0, max(0.0, x))


def propellant_remaining_fraction(
    ctx: AnalysisContext, propellant_kg: float, dv_ms: float
) -> float:
    """Fraction of the loaded propellant left after ``dv_ms`` (rocket equation, R13 masses)."""
    dry = ctx.mass.dry_kg
    available = ctx.maneuvers.available_ms
    if propellant_kg <= 0.0 or dry <= 0.0 or available <= 0.0:
        return 0.0
    if dv_ms <= 0.0:
        return 1.0
    ratio = (dry + propellant_kg) / dry
    return _clamp01((ratio ** (1.0 - dv_ms / available) - 1.0) / (ratio - 1.0))


@dataclass(frozen=True)
class Checkpoint:
    mission_day: float
    phase: Phase
    kind: Literal["transition", "maneuver", "observation", "contact", "event"]
    contact_index: int | None = None


@dataclass(frozen=True)
class TelemetryOverlay:
    """Event effects shown in telemetry (see the module docstring)."""

    event_days: tuple[float, ...] = ()
    soc_dips: Mapping[float, float] = field(default_factory=dict)  # day -> summed delta
    propellant_steps: tuple[tuple[float, float], ...] = ()  # (day, fraction delta)
    buffer_losses: tuple[tuple[float, float], ...] = ()  # (day, lost bits)
    end_day: float | None = None  # termination day


def base_soc(ctx: AnalysisContext, schedule: PhaseSchedule, day: float) -> float:
    """Battery SoC the telemetry shows on ``day`` before any event dip."""
    if day <= 0.0:
        return 1.0
    science = _soc(ctx, "science")
    cruise = _soc(ctx, "cruise")
    if schedule.phase_at(day) == "science-ops" and science is not None:
        return science
    if cruise is not None:
        return cruise
    return science if science is not None else 0.0


def _soc(ctx: AnalysisContext, prefix: str) -> float | None:
    vals = [p.soc_end_fraction for p in ctx.energy.per_phase if p.id.startswith(prefix)]
    return _clamp01(min(vals)) if vals else None


def _buffer_fill(ctx: AnalysisContext, day: float) -> float:
    t = day_to_s(day)
    bits = 0.0
    for ts, b in ctx.data.buffer_timeline:
        if ts <= t:
            bits = b
        else:
            break
    return _clamp01(bits / ctx.buffer_capacity_bits) if ctx.buffer_capacity_bits > 0 else 0.0


def checkpoints(
    state: MissionState,
    schedule: PhaseSchedule,
    has_burn: bool,
    overlay: TelemetryOverlay | None = None,
) -> list[Checkpoint]:
    ops = state.operations
    end = overlay.end_day if overlay is not None else None
    raw: list[tuple[float, int, int, Checkpoint]] = []
    for i, (phase, day) in enumerate(schedule.transitions):
        if end is not None and (phase == "complete" or day > end):
            continue
        raw.append((day, 0, i, Checkpoint(day, phase, "transition")))
    if has_burn:
        day = schedule.arrival_day
        raw.append((day, 1, 0, Checkpoint(day, schedule.phase_at(day), "maneuver")))
    for i, o in enumerate(ops.observation_plan):
        cp = Checkpoint(o.start_day, schedule.phase_at(o.start_day), "observation")
        raw.append((o.start_day, 2, i, cp))
    for i, d in enumerate(ops.downlink_plan):
        cp = Checkpoint(d.start_day, schedule.phase_at(d.start_day), "contact", i)
        raw.append((d.start_day, 3, i, cp))
    if overlay is not None:
        for i, day in enumerate(overlay.event_days):
            raw.append((day, 4, i, Checkpoint(day, schedule.phase_at(day), "event")))
    out = [c for *_, c in sorted(raw, key=lambda r: r[:3])]
    if end is not None:
        out = [c for c in out if c.mission_day <= end]
        out.append(Checkpoint(end, "terminated", "transition"))
    return out


def telemetry_samples(
    state: MissionState,
    schedule: PhaseSchedule,
    ctx: AnalysisContext,
    *,
    propellant_kg: float,
    pointing_accuracy_deg: float,
    overlay: TelemetryOverlay | None = None,
) -> tuple[TelemetrySample, ...]:
    per = ctx.maneuvers.per_maneuver
    burn_dv = per[-1][1] if per else 0.0
    after_burn = propellant_remaining_fraction(ctx, propellant_kg, burn_dv)
    before_burn = propellant_remaining_fraction(ctx, propellant_kg, 0.0)
    science_soc = _soc(ctx, "science")
    fallback_soc = _soc(ctx, "cruise")
    if fallback_soc is None:  # the ledger always has a cruise or a science cycle
        fallback_soc = science_soc if science_soc is not None else 0.0

    out: list[TelemetrySample] = []

    def add(cp: Checkpoint, channel: str, value: float, fidelity: Fidelity) -> None:
        out.append(
            TelemetrySample(
                channel=channel,
                unit=TELEMETRY_UNITS[channel],
                mission_day=cp.mission_day,
                value=value,
                fidelity=fidelity,
                phase=cp.phase,
            )
        )

    ov = overlay or TelemetryOverlay()
    for cp in checkpoints(state, schedule, bool(per), overlay):
        if cp.kind == "transition" and cp.phase == "launch-deployment":
            add(cp, "battery_soc", 1.0, "gameplay-estimate")
        else:
            soc = science_soc if cp.phase == "science-ops" and science_soc is not None else None
            value = soc if soc is not None else fallback_soc
            if cp.kind == "event" and cp.mission_day in ov.soc_dips:
                add(cp, "battery_soc", _clamp01(value + ov.soc_dips[cp.mission_day]), "derived")
            else:
                add(cp, "battery_soc", value, "derived")
        # the burn is flown at arrival; a phase entered on that same day is shown before it
        burned = bool(per) and (
            cp.mission_day > schedule.arrival_day
            or (cp.mission_day == schedule.arrival_day and cp.kind != "transition")
        )
        prop = after_burn if burned else before_burn
        prop += sum(d for t, d in ov.propellant_steps if t <= cp.mission_day)
        add(cp, "propellant_fraction", _clamp01(prop), "derived")
        fill = _buffer_fill(ctx, cp.mission_day)
        lost = sum(b for t, b in ov.buffer_losses if t <= cp.mission_day)
        if lost > 0.0 and ctx.buffer_capacity_bits > 0:
            fill = _clamp01(fill - lost / ctx.buffer_capacity_bits)
        add(cp, "buffer_fill", fill, "derived")
        if cp.contact_index is not None:
            add(cp, "link_margin_db", ctx.contact_links[cp.contact_index].margin_db, "derived")
        add(cp, "pointing_error_deg", pointing_accuracy_deg, "gameplay-estimate")
    return tuple(out)


__all__ = [
    "TELEMETRY_ASSUMPTIONS",
    "TELEMETRY_CHANNELS",
    "TELEMETRY_UNITS",
    "Checkpoint",
    "TelemetryOverlay",
    "base_soc",
    "checkpoints",
    "propellant_remaining_fraction",
    "telemetry_samples",
]

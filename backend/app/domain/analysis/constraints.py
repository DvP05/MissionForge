"""Hard feasibility constraints (architecture 7.2-7.5, 7.11; prod 8.4). Pure.

Status mapping: a hard violation is ``"fail"`` (=> infeasible, never mission-ready); a
design inside every limit but below its configured margin is ``"warning"`` (prod "Watch");
thermal is passed through and can never be ``"pass"``; a constraint that cannot be
evaluated is ``"not-modelled"`` (never ``"pass"``). Constraints are separate from the
score: nothing here depends on, or is offset by, the weighted score.
"""

from collections.abc import Sequence

from app.domain.analysis.context import AnalysisContext
from app.schemas.analysis import ConstraintResult, ConstraintStatus, Feasibility, SuggestedAction
from app.schemas.units import Provenance, Quantity, Unit

MODEL_ID = "constraints-v1"

CONSTRAINT_ASSUMPTIONS: tuple[str, ...] = (
    "Hard gates (status 'fail' => infeasible): launch mass, delta-v with reserve, peak power, "
    "energy closure and battery reserve, data-buffer overflow, trajectory validity, mandatory "
    "science capability, budget, catalogue compatibility, and a downlink where every planned "
    "contact has negative link margin.",
    "Warnings (prod 'Watch'): within the limit but below the configured margin, partial "
    "link-margin failure, data return below generated x (1 + data margin), collected-but-"
    "unreturned mandatory science.",
    "Thermal is qualitative: it is passed through unchanged and is never 'pass'.",
    "Mass: the physical (wet) mass must fit the launch limit; allocated mass (wet x (1 + "
    "margin)) over the limit is a warning. Without a launch limit both are 'not-modelled'.",
    "Data return compares total downlink capacity (rate x duration x protocol efficiency x "
    "availability) with generated data x (1 + data margin), and flags any generated data "
    "that is not downlinked.",
    "mission_ready requires feasibility 'feasible': a marginal design (any warning) is not "
    "mission-ready.",
    "Suggested actions are rule-based hints, not an optimiser's guarantee.",
)

_SRC = "MISSIONFORGE constraint model"
_SEV_FAIL = 3
_SEV_WATCH = 2
_SEV_MINOR = 1
_MS_PER_KM_S = 1000.0


def _q(value: float, unit: Unit) -> Quantity:
    return Quantity(
        value=value,
        unit=unit,
        provenance=Provenance(fidelity="derived", source_name=_SRC, assumptions=()),
    )


def _act(action_id: str, label: str, effect: str) -> SuggestedAction:
    return SuggestedAction(action_id=action_id, label=label, expected_effect=effect)


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator > 0.0 else None


def _result(
    cid: str,
    label: str,
    status: ConstraintStatus,
    explanation: str,
    *,
    actual: Quantity | None = None,
    limit: Quantity | None = None,
    margin: float | None = None,
    severity: int = 0,
    subsystems: Sequence[str] = (),
    actions: Sequence[SuggestedAction] = (),
) -> ConstraintResult:
    return ConstraintResult(
        id=cid,
        label=label,
        status=status,
        actual=actual,
        limit=limit,
        margin_fraction=margin,
        severity=severity if status in ("fail", "warning") else 0,
        explanation=explanation,
        impacted_subsystems=list(subsystems),
        suggested_actions=list(actions),
    )


def _mass(ctx: AnalysisContext) -> list[ConstraintResult]:
    limit = ctx.limits.launch_mass_limit_kg
    m = ctx.mass
    if limit is None:
        why = "no launch mass limit is configured, so mass cannot be checked against one"
        return [
            _result("mass-launch-limit", "Launch mass limit", "not-modelled", why),
            _result("mass-margin", "Mass margin", "not-modelled", why),
        ]
    actions = [
        _act("larger-launch-vehicle", "Choose a larger launch vehicle", "Raises the mass limit."),
        _act("reduce-propellant", "Reduce propellant or payload mass", "Lowers wet mass."),
    ]
    wet_margin = (limit - m.wet_kg) / limit
    if m.wet_kg > limit:
        launch = _result(
            "mass-launch-limit", "Launch mass limit", "fail",
            f"Wet mass {m.wet_kg:.1f} kg exceeds the launch limit {limit:.1f} kg.",
            actual=_q(m.wet_kg, "kg"), limit=_q(limit, "kg"), margin=wet_margin,
            severity=_SEV_FAIL, subsystems=["launch", "mass"], actions=actions,
        )  # fmt: skip
    else:
        launch = _result(
            "mass-launch-limit", "Launch mass limit", "pass",
            f"Wet mass {m.wet_kg:.1f} kg is within the launch limit {limit:.1f} kg.",
            actual=_q(m.wet_kg, "kg"), limit=_q(limit, "kg"), margin=wet_margin,
        )  # fmt: skip
    margin = (limit - m.allocated_kg) / limit
    if m.allocated_kg > limit:
        held = _result(
            "mass-margin", "Mass margin", "warning",
            f"Allocated mass {m.allocated_kg:.1f} kg (wet x (1 + "
            f"{ctx.limits.mass_margin_fraction:.0%} margin)) exceeds the limit {limit:.1f} kg.",
            actual=_q(m.allocated_kg, "kg"), limit=_q(limit, "kg"), margin=margin,
            severity=_SEV_WATCH, subsystems=["launch", "mass"], actions=actions,
        )  # fmt: skip
    else:
        held = _result(
            "mass-margin", "Mass margin", "pass",
            f"Allocated mass {m.allocated_kg:.1f} kg is within the limit {limit:.1f} kg.",
            actual=_q(m.allocated_kg, "kg"), limit=_q(limit, "kg"), margin=margin,
        )  # fmt: skip
    return [launch, held]


def _delta_v(ctx: AnalysisContext) -> ConstraintResult:
    b = ctx.maneuvers
    reserve = ctx.limits.delta_v_margin_km_per_s * _MS_PER_KM_S
    needed = b.required_ms + reserve
    margin = _ratio(b.margin_ms, needed)
    if b.margin_ms < 0.0:
        consumer = (
            f" The reserve is first consumed by {b.reserve_consumed_by}."
            if b.reserve_consumed_by
            else ""
        )
        return _result(
            "delta-v-margin", "Delta-v margin", "fail",
            f"Available delta-v {b.available_ms:.0f} m/s is below required "
            f"{b.required_ms:.0f} m/s plus reserve {reserve:.0f} m/s.{consumer}",
            actual=_q(b.available_ms, "m/s"), limit=_q(needed, "m/s"), margin=margin,
            severity=_SEV_FAIL, subsystems=["propulsion", "trajectory", "mass"],
            actions=[
                _act("add-propellant", "Add propellant", "Raises available delta-v."),
                _act("swap-propulsion", "Choose higher-Isp propulsion", "Raises delta-v per kg."),
            ],
        )  # fmt: skip
    return _result(
        "delta-v-margin", "Delta-v margin", "pass",
        f"Available delta-v {b.available_ms:.0f} m/s covers required {b.required_ms:.0f} m/s "
        f"plus reserve {reserve:.0f} m/s.",
        actual=_q(b.available_ms, "m/s"), limit=_q(needed, "m/s"), margin=margin,
    )  # fmt: skip


def _peak_power(ctx: AnalysisContext) -> ConstraintResult:
    peak, supply, pm = ctx.peak_power_w, ctx.supply_power_w, ctx.limits.power_margin_fraction
    margin = (supply - peak) / supply if supply > 0.0 else (0.0 if peak <= 0.0 else -1.0)
    actions = [
        _act("swap-power", "Choose a larger power system", "Raises regulated peak supply."),
        _act("reduce-duty-cycle", "Reduce simultaneous loads or duty cycle", "Lowers peak load."),
    ]
    actual, limit = _q(peak, "W"), _q(supply, "W")
    if peak > supply:
        return _result(
            "peak-power", "Peak power", "fail",
            f"Peak load {peak:.1f} W exceeds the regulated supply {supply:.1f} W.",
            actual=actual, limit=limit, margin=margin, severity=_SEV_FAIL,
            subsystems=["power", "payload"], actions=actions,
        )  # fmt: skip
    if peak * (1.0 + pm) > supply:
        return _result(
            "peak-power", "Peak power", "warning",
            f"Peak load {peak:.1f} W fits the supply {supply:.1f} W but not with the "
            f"{pm:.0%} power margin.",
            actual=actual, limit=limit, margin=margin, severity=_SEV_WATCH,
            subsystems=["power", "payload"], actions=actions,
        )  # fmt: skip
    return _result(
        "peak-power", "Peak power", "pass",
        f"Peak load {peak:.1f} W is within the supply {supply:.1f} W with margin.",
        actual=actual, limit=limit, margin=margin,
    )  # fmt: skip


def energy_margin_fraction(ctx: AnalysisContext) -> float | None:
    """Solar energy over the period relative to consumed energy, minus one."""
    gen = sum(p.generation_wh for p in ctx.energy.per_phase)
    cons = sum(p.consumption_wh for p in ctx.energy.per_phase)
    return gen / cons - 1.0 if cons > 0.0 else None


def _energy(ctx: AnalysisContext) -> list[ConstraintResult]:
    gen = sum(p.generation_wh for p in ctx.energy.per_phase)
    cons = sum(p.consumption_wh for p in ctx.energy.per_phase)
    pm = ctx.limits.power_margin_fraction
    need = cons * (1.0 + pm)
    reasons: list[str] = []
    if gen < need:
        reasons.append(
            f"generated {gen:.1f} Wh is below consumed {cons:.1f} Wh plus {pm:.0%} margin"
        )
    if not ctx.energy.closes:
        reasons.append(
            f"battery state of charge falls to {ctx.energy.min_soc_fraction:.0%}, below the "
            f"{ctx.energy.soc_floor_fraction:.0%} floor"
        )
    solar = _act("swap-power", "Choose a larger solar array", "Raises generated energy.")
    battery_action = _act("larger-battery", "Choose a larger battery", "Covers eclipse and draw.")
    duty = _act("reduce-duty-cycle", "Reduce instrument duty cycle", "Lowers consumed energy.")
    if reasons:
        closure = _result(
            "energy-closure", "Energy closure", "fail",
            "Energy does not close: " + "; ".join(reasons) + ".",
            actual=_q(gen, "Wh"), limit=_q(need, "Wh"), margin=energy_margin_fraction(ctx),
            severity=_SEV_FAIL, subsystems=["power"], actions=[solar, battery_action, duty],
        )  # fmt: skip
    else:
        closure = _result(
            "energy-closure", "Energy closure", "pass",
            f"Generated {gen:.1f} Wh covers consumed {cons:.1f} Wh plus {pm:.0%} margin.",
            actual=_q(gen, "Wh"), limit=_q(need, "Wh"), margin=energy_margin_fraction(ctx),
        )  # fmt: skip

    soc, floor = ctx.energy.min_soc_fraction, ctx.energy.soc_floor_fraction
    soc_margin = soc - floor
    if not ctx.energy.closes:
        battery = _result(
            "battery-reserve", "Battery reserve", "fail",
            f"Minimum battery state of charge {soc:.0%} is below the {floor:.0%} floor.",
            actual=_q(soc, "fraction"), limit=_q(floor, "fraction"), margin=soc_margin,
            severity=_SEV_FAIL, subsystems=["power"], actions=[battery_action, duty],
        )  # fmt: skip
    elif soc_margin < pm:
        battery = _result(
            "battery-reserve", "Battery reserve", "warning",
            f"Minimum battery state of charge {soc:.0%} is only {soc_margin:.0%} above the "
            f"{floor:.0%} floor, below the {pm:.0%} margin.",
            actual=_q(soc, "fraction"), limit=_q(floor, "fraction"), margin=soc_margin,
            severity=_SEV_WATCH, subsystems=["power"], actions=[battery_action, duty],
        )  # fmt: skip
    else:
        battery = _result(
            "battery-reserve", "Battery reserve", "pass",
            f"Minimum battery state of charge {soc:.0%} stays above the {floor:.0%} floor.",
            actual=_q(soc, "fraction"), limit=_q(floor, "fraction"), margin=soc_margin,
        )  # fmt: skip
    return [closure, battery]


def _data_buffer(ctx: AnalysisContext) -> ConstraintResult:
    d, cap = ctx.data, ctx.buffer_capacity_bits
    margin = (cap - d.peak_buffer_bits) / cap if cap > 0.0 else None
    actions = [
        _act("swap-cdh", "Choose a larger data buffer", "Holds more data between contacts."),
        _act("reduce-duty-cycle", "Reduce observation duty cycle", "Generates less data."),
        _act("add-contacts", "Plan more downlink contacts", "Drains the buffer sooner."),
    ]
    actual, limit = _q(d.peak_buffer_bits, "bit"), _q(cap, "bit")
    if d.overflow_bits > 0.0:
        status: ConstraintStatus = "warning" if ctx.overflow_accepted else "fail"
        accepted = " (data loss accepted by the player)" if ctx.overflow_accepted else ""
        return _result(
            "data-buffer", "Data buffer", status,
            f"Buffer overflows: {d.overflow_bits:.3g} bit lost; peak {d.peak_buffer_bits:.3g} bit "
            f"against capacity {cap:.3g} bit{accepted}.",
            actual=actual, limit=limit, margin=margin,
            severity=_SEV_WATCH if ctx.overflow_accepted else _SEV_FAIL,
            subsystems=["data", "cdh"], actions=actions,
        )  # fmt: skip
    if margin is not None and margin < ctx.limits.data_margin_fraction:
        return _result(
            "data-buffer", "Data buffer", "warning",
            f"Peak buffer {d.peak_buffer_bits:.3g} bit leaves only {margin:.0%} headroom of "
            f"{cap:.3g} bit, below the {ctx.limits.data_margin_fraction:.0%} data margin.",
            actual=actual, limit=limit, margin=margin, severity=_SEV_MINOR,
            subsystems=["data", "cdh"], actions=actions,
        )  # fmt: skip
    return _result(
        "data-buffer", "Data buffer", "pass",
        f"Peak buffer {d.peak_buffer_bits:.3g} bit fits capacity {cap:.3g} bit with no overflow.",
        actual=actual, limit=limit, margin=margin,
    )  # fmt: skip


def _link_margin(ctx: AnalysisContext) -> ConstraintResult:
    margins = [lk.margin_db for lk in ctx.contact_links]
    if not margins:
        return _result(
            "link-margin", "Link margin", "not-modelled",
            "no downlink contacts are planned, so no link margin exists to check",
        )  # fmt: skip
    worst = min(margins)
    bad = sum(1 for m in margins if m < 0.0)
    actions = [
        _act("swap-comms", "Upgrade communications (higher-gain antenna)", "Raises link margin."),
        _act("reduce-downlink-rate", "Plan a lower downlink rate", "Raises Eb/N0 per bit."),
    ]
    actual, limit = _q(worst, "dB"), _q(0.0, "dB")
    if bad == len(margins):
        return _result(
            "link-margin", "Link margin", "fail",
            f"Link margin is negative on all {bad} planned contacts (worst {worst:.1f} dB, "
            "limit 0 dB): no data can be downlinked.",
            actual=actual, limit=limit, severity=_SEV_FAIL,
            subsystems=["communications", "data"], actions=actions,
        )  # fmt: skip
    if bad:
        return _result(
            "link-margin", "Link margin", "warning",
            f"Link margin is negative on {bad} of {len(margins)} planned contacts (worst "
            f"{worst:.1f} dB, limit 0 dB); those contacts return no data.",
            actual=actual, limit=limit, severity=_SEV_MINOR,
            subsystems=["communications", "data"], actions=actions,
        )  # fmt: skip
    return _result(
        "link-margin", "Link margin", "pass",
        f"All {len(margins)} planned contacts close (worst margin {worst:.1f} dB).",
        actual=actual, limit=limit,
    )  # fmt: skip


def data_return_margin_fraction(ctx: AnalysisContext) -> float | None:
    """Total downlink capacity relative to generated data, minus one (None if no data)."""
    if ctx.data.generated_bits <= 0.0:
        return None
    capacity = sum(c.capacity_bits for c in ctx.data.per_contact)
    return capacity / ctx.data.generated_bits - 1.0


def _data_return(ctx: AnalysisContext) -> ConstraintResult:
    d = ctx.data
    dm = ctx.limits.data_margin_fraction
    margin = data_return_margin_fraction(ctx)
    if margin is None:
        return _result(
            "data-return", "Data return", "pass",
            "No science data is generated, so there is nothing to return.",
        )  # fmt: skip
    capacity = sum(c.capacity_bits for c in d.per_contact)
    need = d.generated_bits * (1.0 + dm)
    undelivered = d.generated_bits - d.downlinked_bits > 1e-9 * d.generated_bits
    if capacity >= need and not undelivered:
        return _result(
            "data-return", "Data return", "pass",
            f"Downlink capacity {capacity:.3g} bit covers generated {d.generated_bits:.3g} bit "
            "with margin; all generated data is downlinked.",
            actual=_q(capacity, "bit"), limit=_q(need, "bit"), margin=margin,
        )  # fmt: skip
    return _result(
        "data-return", "Data return", "warning",
        f"Downlink capacity {capacity:.3g} bit versus {need:.3g} bit needed (generated "
        f"{d.generated_bits:.3g} bit plus {dm:.0%} margin); only {d.downlinked_bits:.3g} bit is "
        "downlinked, so collected science is not fully returned.",
        actual=_q(capacity, "bit"), limit=_q(need, "bit"), margin=margin,
        severity=_SEV_WATCH, subsystems=["communications", "data", "payload"],
        actions=[
            _act(
                "swap-comms",
                "Upgrade communications (e.g. higher-gain antenna) or reduce observation "
                "duty cycle",
                "Raises downlink capacity or lowers generated data so more science is returned.",
            ),
            _act("reduce-duty-cycle", "Reduce observation duty cycle", "Generates less data."),
            _act("add-contacts", "Plan more or longer downlink contacts", "Adds capacity."),
        ],
    )  # fmt: skip


def _compat(ctx: AnalysisContext) -> list[ConstraintResult]:
    out: list[ConstraintResult] = []
    for issue in ctx.compat_issues:
        slug = f"{issue.code}-{issue.component_id}".lower().replace("_", "-")
        out.append(
            _result(
                f"compat-{slug}",
                f"Compatibility: {issue.component_id}",
                "fail",
                f"{issue.message} (component {issue.component_id}, rule {issue.code}).",
                severity=_SEV_FAIL,
                subsystems=[issue.component_id],
                actions=[
                    _act(
                        "swap-incompatible-component",
                        f"Replace {issue.component_id} with a compatible component",
                        "Removes the compatibility violation.",
                    )
                ],
            )  # fmt: skip
        )
    return out


def _science(ctx: AnalysisContext) -> ConstraintResult:
    no_cap = sorted(r for r, why in ctx.science_missing if why == "no-capability")
    no_ret = sorted(r for r, why in ctx.science_missing if why == "no-returned-data")
    if no_cap:
        return _result(
            "science-mandatory-coverage", "Mandatory science coverage", "fail",
            f"Required measurement(s) {', '.join(no_cap)} have no instrument capability "
            "selected, so the mandatory science cannot be achieved.",
            severity=_SEV_FAIL, subsystems=["payload", "science"],
            actions=[
                _act(
                    "add-instrument",
                    "Add an instrument with the required capability",
                    "Makes the required measurement possible.",
                )
            ],
        )  # fmt: skip
    if no_ret:
        return _result(
            "science-mandatory-coverage", "Mandatory science coverage", "warning",
            f"Required measurement(s) {', '.join(no_ret)} are collected but no data is "
            "returned to Earth.",
            severity=_SEV_WATCH, subsystems=["payload", "data", "communications"],
            actions=[
                _act("swap-comms", "Upgrade communications", "Returns the collected data."),
                _act("add-contacts", "Plan more downlink contacts", "Adds return capacity."),
            ],
        )  # fmt: skip
    return _result(
        "science-mandatory-coverage", "Mandatory science coverage", "pass",
        "Every required measurement has instrument capability and returned data.",
    )  # fmt: skip


def _trajectory(ctx: AnalysisContext) -> ConstraintResult:
    if ctx.trajectory_valid:
        return _result(
            "trajectory-valid", "Trajectory validity", "pass",
            "A valid trajectory option is selected.",
        )  # fmt: skip
    return _result(
        "trajectory-valid", "Trajectory validity", "fail",
        "No valid trajectory option is selected for this destination.",
        severity=_SEV_FAIL, subsystems=["trajectory"],
        actions=[_act("select-trajectory", "Select a valid trajectory option", "Enables delta-v.")],
    )  # fmt: skip


def _budget(ctx: AnalysisContext) -> ConstraintResult:
    total, cap = ctx.cost.total, ctx.limits.maximum_budget_usd
    margin = (cap - total) / cap
    actual, limit = _q(total, "USD"), _q(cap, "USD")
    if total > cap:
        return _result(
            "budget", "Budget", "fail",
            f"Estimated cost ${total:,.0f} exceeds the maximum budget ${cap:,.0f}.",
            actual=actual, limit=limit, margin=margin, severity=_SEV_FAIL,
            subsystems=["cost", "launch"],
            actions=[
                _act("cheaper-launch", "Choose a cheaper launch vehicle", "Lowers launch cost."),
                _act("remove-instrument", "Remove an optional instrument", "Lowers cost."),
            ],
        )  # fmt: skip
    return _result(
        "budget", "Budget", "pass",
        f"Estimated cost ${total:,.0f} is within the maximum budget ${cap:,.0f}.",
        actual=actual, limit=limit, margin=margin,
    )  # fmt: skip


def _thermal(ctx: AnalysisContext) -> ConstraintResult:
    t = ctx.thermal
    if t.status == "pass":  # thermal is qualitative: never a "pass"
        return t.model_copy(
            update={"status": "not-modelled", "severity": 0, "suggested_actions": []}
        )
    return t


def evaluate_constraints(ctx: AnalysisContext) -> list[ConstraintResult]:
    return [
        *_mass(ctx),
        _delta_v(ctx),
        _peak_power(ctx),
        *_energy(ctx),
        _data_buffer(ctx),
        _link_margin(ctx),
        _data_return(ctx),
        *_compat(ctx),
        _science(ctx),
        _trajectory(ctx),
        _budget(ctx),
        _thermal(ctx),
    ]


def feasibility(constraints: Sequence[ConstraintResult]) -> Feasibility:
    if any(c.status == "fail" for c in constraints):
        return "infeasible"
    if any(c.status == "warning" for c in constraints):
        return "marginal"
    return "feasible"


def mission_ready(constraints: Sequence[ConstraintResult]) -> bool:
    """Only a fully 'feasible' design is mission-ready; 'marginal' (any warning) is not."""
    return feasibility(constraints) == "feasible"

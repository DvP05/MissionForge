"""``analyze_mission``: compose every discipline into one MissionAnalysis (architecture 8.3).

Pure and deterministic: the catalogue, the scenario inputs and ``now`` are injected, so
``calculated_at`` is the only field that varies between identical calls.

Flow: resolve -> compatibility -> mass -> propulsion -> power -> comms/data -> science ->
cost / reliability / thermal -> AnalysisContext -> constraints -> feasibility ->
score -> top drivers -> MissionAnalysis (assumptions of every module merged).

Engine conventions (all labelled in ``ORCHESTRATOR_ASSUMPTIONS``):

* Propellant: the tank is loaded to ``propellant_capacity`` (the template tuning assumes a
  full tank); delta-v uses physical masses (R13).
* Spacecraft maneuver: ``trajectory.mission_delta_v_km_per_s`` is a spacecraft maneuver
  for ``scenario-preset`` / ``manual-estimate`` trajectories (the NEO preset encodes its
  0.25 km/s rendezvous burn this way) and informational only for ``jpl-mdesign`` (JPL
  ``dv_tot`` is never added to spacecraft delta-v). The reserve is
  ``MissionConstraints.delta_v_margin_km_per_s``.
* Launch limit: the stricter of ``MissionConstraints.launch_mass_limit_kg`` and the
  selected launch vehicle's ``launch_mass_limit``.
* Peak power: supply is computed per phase (eclipse = battery only) and the phase with
  the smallest supply - peak margin is the one passed to the constraints.
* Power: one representative cycle (``power_cycle_s``, default one day) per phase -- cruise
  and science (the span of the observation plan) -- each split into sunlit and eclipse
  parts. Loads use phase-average duty cycles; bus, ADCS, thermal and C&DH are always on.
* Comms: one link budget per planned contact at min(planned rate, radio max rate), the
  same rate the data ledger uses; range from ``ScenarioInputs.reference_earth_range_m``.

Error policy: a design problem (unknown catalogue id, missing catalogue parameter, invalid
model input, or a pydantic ValidationError from a contract model built inside the
analysis) never escapes as an exception. It becomes a MissionAnalysis with a single
failing constraint (``catalog-item-not-found`` or ``model-input-invalid``, explanation
naming the error code and field) and zero placeholder budgets labelled ``not-modelled``;
the contract represents this (fail => infeasible, never mission-ready).
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from pydantic import ValidationError

from app.domain.analysis import comms as comms_mod
from app.domain.analysis._params import param_value
from app.domain.analysis.comms import LinkResult, link_budget, link_input_from_components
from app.domain.analysis.constraints import (
    CONSTRAINT_ASSUMPTIONS,
    data_return_margin_fraction,
    energy_margin_fraction,
    evaluate_constraints,
    feasibility,
    mission_ready,
)
from app.domain.analysis.context import BATTERY_DISCHARGE_EFFICIENCY, AnalysisContext
from app.domain.analysis.cost import CostParams, cost_estimate
from app.domain.analysis.data import (
    contact_events_from_plan,
    data_ledger,
    observation_events_from_plan,
)
from app.domain.analysis.drivers import top_drivers
from app.domain.analysis.mass import compute_mass_budget
from app.domain.analysis.power import (
    EnergyLedger,
    Load,
    PowerPhase,
    array_generation_w,
    average_power_w,
    battery_from_component,
    energy_ledger,
    peak_power_w,
    solar_array_params,
)
from app.domain.analysis.propulsion import Maneuver, ManeuverBudget, maneuver_budget
from app.domain.analysis.reliability import RELIABILITY_ASSUMPTIONS, reliability
from app.domain.analysis.science import (
    missing_reasons,
    pointing_ok_for,
    science_assumptions,
    science_coverage,
)
from app.domain.analysis.score import SCORE_ASSUMPTIONS, WEIGHTS, score_preview
from app.domain.analysis.thermal import THERMAL_ASSUMPTIONS, ThermalExposure, thermal_check
from app.domain.catalog.compat import check_compatibility
from app.domain.catalog.loader import Catalog
from app.domain.catalog.resolver import (
    CatalogItemNotFound,
    ResolvedArchitecture,
    resolve_architecture,
)
from app.domain.errors import DomainValidationError
from app.domain.units.conversions import day_to_s, ms_to_kms
from app.domain.units.guards import require_finite, require_positive
from app.schemas.analysis import (
    BudgetAnalysis,
    ConstraintResult,
    MissionAnalysis,
    ReliabilityAnalysis,
    ScienceAnalysis,
    ScoreBreakdown,
    ScoreDimension,
    SuggestedAction,
)
from app.schemas.catalog import CatalogComponent
from app.schemas.mission import MissionConstraints, MissionState
from app.schemas.templates import ScenarioTemplate
from app.schemas.trajectory import TrajectorySelection
from app.schemas.units import Provenance, Quantity, Uncertainty, Unit

ENGINE_VERSION = "0.1.0"
MODEL_ID = "analysis-v1"

# gameplay-estimate: how long each spacecraft maneuver runs the propulsion load.
MANEUVER_BURN_S = 3600.0
# gameplay-estimate: the battery can deliver its capacity in one hour (1C) on top of the
# array output, so regulated peak supply = array generation + capacity x 1 /h.
BATTERY_PEAK_C_RATE_PER_H = 1.0

ORCHESTRATOR_ASSUMPTIONS: tuple[str, ...] = (
    "Propellant tank is loaded to its full capacity; propellant sizing is not optimised.",
    "Trajectory mission delta-v counts as a spacecraft maneuver only for scenario-preset and "
    "manual-estimate trajectories; JPL trajectory figures are informational.",
    "Launch mass limit = the stricter of the mission constraint and the launch vehicle limit.",
    "Each maneuver runs the propulsion load for 1 h (gameplay-estimate).",
    "Power ledger: one representative cycle per phase (cruise, then science = span of the "
    "observation plan), each split into sunlit and eclipse parts, with phase-average duty "
    "cycles; bus, ADCS, thermal and C&DH loads are always on.",
    "Regulated peak supply per phase = array output + battery capacity x 1C (gameplay-"
    "estimate); in eclipse only the battery term applies. The phase with the smallest "
    "supply - peak margin is checked.",
    f"Battery discharge efficiency = {BATTERY_DISCHARGE_EFFICIENCY} (gameplay-estimate).",
    "Average power = sum(P x mission-average duty cycle) over every powered component.",
    "Each measurement is observed by the capable selected instrument with the highest data "
    "rate; plan items without a capable instrument generate no data and draw no power.",
    "Link budget per contact at min(planned rate, radio max rate), the rate the ledger uses.",
)


@dataclass(frozen=True)
class ScenarioDefaults:
    sun_distance_au: float
    thermal_exposure: ThermalExposure | None


# gameplay-estimate per-scenario environment (templates carry no sun distance / exposure).
SCENARIO_DEFAULTS: dict[str, ScenarioDefaults] = {
    "neo-rendezvous": ScenarioDefaults(1.3, "cold"),
    "lunar-polar-scout": ScenarioDefaults(1.0, "cold"),
    "earth-observation": ScenarioDefaults(1.0, "benign"),
}
_FALLBACK_DEFAULTS = ScenarioDefaults(1.0, None)


@dataclass(frozen=True)
class ScenarioInputs:
    """Scenario environment passed into the analysis explicitly (never read from state)."""

    reference_earth_range_m: float
    sun_distance_au: float = 1.0
    thermal_exposure: ThermalExposure | None = None
    cost_params: CostParams = field(default_factory=CostParams)
    eclipse_fraction: float = 0.0  # fraction of each power cycle in eclipse, [0, 1)
    power_cycle_s: float = 86_400.0  # representative power cycle length (one day)
    assumptions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_positive(self.reference_earth_range_m, "reference_earth_range_m")
        require_positive(self.sun_distance_au, "sun_distance_au")
        require_positive(self.power_cycle_s, "power_cycle_s")
        f = require_finite(self.eclipse_fraction, "eclipse_fraction")
        if not 0.0 <= f < 1.0:
            raise DomainValidationError(
                "INVALID_ECLIPSE_FRACTION", "eclipse_fraction", "must be in [0, 1)"
            )


def scenario_inputs_from_template(template: ScenarioTemplate) -> ScenarioInputs:
    d = SCENARIO_DEFAULTS.get(template.scenario_id, _FALLBACK_DEFAULTS)
    exposure = d.thermal_exposure or "none"
    return ScenarioInputs(
        reference_earth_range_m=template.reference_earth_range_m,
        sun_distance_au=d.sun_distance_au,
        thermal_exposure=d.thermal_exposure,
        assumptions=(
            f"Scenario {template.scenario_id}: sun distance {d.sun_distance_au:.1f} AU and "
            f"thermal exposure '{exposure}' are gameplay-estimate defaults; no eclipse is "
            "modelled for the starter scenarios.",
            f"Earth range for the link budget is the template reference range "
            f"{template.reference_earth_range_m:.3g} m (gameplay-estimate).",
        ),
    )


# --- helpers ------------------------------------------------------------------------


def _p(comp: CatalogComponent, key: str, unit: str) -> float:
    return param_value(comp, key, unit, field=f"{comp.id}.{key}")


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _maneuvers(traj: TrajectorySelection) -> list[Maneuver]:
    dv = traj.mission_delta_v_km_per_s
    if dv is None:
        return []
    source: Literal["spacecraft", "trajectory-info"] = (
        "trajectory-info" if traj.provider == "jpl-mdesign" else "spacecraft"
    )
    return [Maneuver(id=f"{traj.option_id}-delta-v", dv_ms=dv * 1000.0, source=source)]


def _trajectory_valid(traj: TrajectorySelection) -> bool:
    if not traj.option_id.strip():
        return False
    if traj.arrival_date is not None and traj.arrival_date < traj.departure_date:
        return False
    return traj.time_of_flight_days is None or traj.time_of_flight_days >= 0.0


def _assign_instruments(
    state: MissionState, resolved: ResolvedArchitecture
) -> dict[str, CatalogComponent]:
    """Measurement id -> the capable instrument with the highest data rate (id breaks ties)."""
    out: dict[str, CatalogComponent] = {}
    for obj in state.science_objectives:
        for req in obj.required_measurements:
            cap = req.instrument_capability
            capable = [i for i in resolved.instruments if cap in i.capabilities]
            if capable:
                out[req.id] = min(capable, key=lambda i: (-_p(i, "data_rate", "bit/s"), i.id))
    return out


@dataclass(frozen=True)
class _Power:
    avg_w: float
    peak_w: float
    supply_w: float
    ledger: EnergyLedger


def _power(
    state: MissionState,
    resolved: ResolvedArchitecture,
    assigned: dict[str, CatalogComponent],
    n_maneuvers: int,
    scenario: ScenarioInputs,
) -> _Power:
    ops = state.operations
    mission_s = day_to_s(ops.mission_duration_days)

    # (component, intervals[(start, end, duty)]) for intermittent loads
    obs: dict[str, list[tuple[float, float, float]]] = {}
    for item in ops.observation_plan:
        inst = assigned.get(item.measurement_id)
        if inst is not None:
            start = day_to_s(item.start_day)
            obs.setdefault(inst.id, []).append(
                (start, start + item.duration_hours * 3600.0, item.duty_cycle)
            )
    contacts = [
        (day_to_s(d.start_day), day_to_s(d.start_day) + d.duration_minutes * 60.0)
        for d in ops.downlink_plan
    ]
    burn_s = n_maneuvers * MANEUVER_BURN_S
    spans = [(s, e) for ivs in obs.values() for s, e, _ in ivs]
    window = (min(s for s, _ in spans), max(e for _, e in spans)) if spans else None
    sci_s = window[1] - window[0] if window else 0.0
    cruise_s = max(0.0, mission_s - sci_s)

    always_on = (resolved.bus, resolved.adcs, resolved.thermal, resolved.cdh)
    comm, prop = resolved.communications, resolved.propulsion

    def active(lo: float, hi: float) -> tuple[float, dict[str, float]]:
        """Active seconds inside [lo, hi): contacts, and observation (s x duty) per inst."""
        c = sum(_overlap(s, e, lo, hi) for s, e in contacts)
        o = {k: sum(_overlap(s, e, lo, hi) * d for s, e, d in v) for k, v in obs.items()}
        return c, o

    def loads(dur: float, contact_s: float, obs_s: dict[str, float], burn: float) -> list[Load]:
        def duty(x: float) -> float:
            return min(1.0, x / dur) if dur > 0.0 else 0.0

        out = [Load(c.id, _p(c, "power_w", "W"), 1.0) for c in always_on]
        out.append(Load(comm.id, _p(comm, "power_w", "W"), duty(contact_s)))
        out.append(Load(prop.id, _p(prop, "power_w", "W"), duty(burn)))
        out.extend(
            Load(i.id, _p(i, "power_w", "W"), duty(obs_s.get(i.id, 0.0)))
            for i in resolved.instruments
        )
        return out

    total_contact, total_obs = active(-float("inf"), float("inf"))
    mission_loads = loads(mission_s, total_contact, total_obs, burn_s)

    phase_loads: list[tuple[str, list[Load]]] = []
    if window is not None:
        sci_c, sci_o = active(*window)
        cruise_o = {k: total_obs[k] - sci_o.get(k, 0.0) for k in total_obs}
        if cruise_s > 0.0:
            phase_loads.append(("cruise", loads(cruise_s, total_contact - sci_c, cruise_o, burn_s)))
        phase_loads.append(("science", loads(sci_s, sci_c, sci_o, 0.0 if cruise_s else burn_s)))
    else:
        phase_loads.append(("cruise", mission_loads))

    power = resolved.power
    array = solar_array_params(power)
    generation = array_generation_w(
        array.array_power_at_1au_w, scenario.sun_distance_au, array.eps_efficiency, 0.0
    )
    battery = battery_from_component(power, discharge_efficiency=BATTERY_DISCHARGE_EFFICIENCY)
    t, f = scenario.power_cycle_s, scenario.eclipse_fraction
    phases: list[PowerPhase] = []
    for pid, ls in phase_loads:
        phases.append(PowerPhase(f"{pid}-sunlit", t * (1.0 - f), generation, tuple(ls)))
        if f > 0.0:
            phases.append(PowerPhase(f"{pid}-eclipse", t * f, 0.0, tuple(ls)))
    # Peak vs supply per phase: sunlit = array + battery 1C, eclipse = battery 1C only.
    # The phase with the smallest (supply - peak) margin is the one checked.
    battery_w = battery.capacity_wh * BATTERY_PEAK_C_RATE_PER_H
    pairs = [(peak_power_w(list(ph.loads)), ph.generation_w + battery_w) for ph in phases]
    peak, supply = min(pairs, key=lambda ps: ps[1] - ps[0])
    return _Power(
        avg_w=average_power_w(mission_loads),
        peak_w=peak,
        supply_w=supply,
        ledger=energy_ledger(phases, battery),
    )


@dataclass(frozen=True)
class _Built:
    ctx: AnalysisContext
    maneuvers: ManeuverBudget
    propellant_kg: float
    assumptions: tuple[str, ...]


def _build(state: MissionState, catalog: Catalog, scenario: ScenarioInputs) -> _Built:
    resolved = resolve_architecture(state.architecture, catalog)
    compat = tuple(check_compatibility(resolved.all_components()))

    configured = state.constraints.launch_mass_limit_kg
    vehicle = _p(resolved.launch, "launch_mass_limit", "kg")
    limit = vehicle if configured is None else min(configured, vehicle)
    limits = MissionConstraints.model_validate(
        {**state.constraints.model_dump(), "launch_mass_limit_kg": limit}
    )

    propellant = _p(resolved.propulsion, "propellant_capacity", "kg")
    mass = compute_mass_budget(resolved, propellant, limits.mass_margin_fraction, limit)
    maneuvers = _maneuvers(state.trajectory)
    budget = maneuver_budget(
        resolved.propulsion,
        mass.dry_kg,
        maneuvers,
        limits.delta_v_margin_km_per_s * 1000.0,
        propellant_kg=propellant,
    )

    assigned = _assign_instruments(state, resolved)
    n_burns = sum(1 for m in maneuvers if m.source == "spacecraft")
    pw = _power(state, resolved, assigned, n_burns, scenario)

    ops = state.operations
    comm, ground = resolved.communications, resolved.ground
    rng = scenario.reference_earth_range_m
    observed = tuple(i for i in ops.observation_plan if i.measurement_id in assigned)
    rates = {m: _p(inst, "data_rate", "bit/s") for m, inst in assigned.items()}
    ledger = data_ledger(
        observation_events_from_plan(observed, rates),
        contact_events_from_plan(ops.downlink_plan, comm, ground, range_m=rng),
        _p(resolved.cdh, "storage", "bit"),
    )
    max_rate = _p(comm, "max_data_rate", "bit/s")
    links: tuple[LinkResult, ...] = tuple(
        link_budget(
            link_input_from_components(
                comm, ground, range_m=rng,
                bit_rate_bps=min(d.data_rate_bits_per_second, max_rate),
            )
        )
        for d in ops.downlink_plan
    )  # fmt: skip

    pointing = _p(resolved.adcs, "pointing_accuracy", "deg")
    power_ok = pw.peak_w <= pw.supply_w and pw.ledger.closes
    objectives = state.science_objectives
    science = science_coverage(
        objectives, resolved.instruments, ops.observation_plan, ledger,
        pointing_accuracy_deg=pointing, power_ok=power_ok,
        instrument_by_measurement=assigned,
    )  # fmt: skip
    missing = missing_reasons(
        objectives, resolved.instruments, ops.observation_plan, ledger,
        pointing_accuracy_deg=pointing, power_ok=power_ok,
        instrument_by_measurement=assigned,
    )  # fmt: skip
    pointing_ok = pointing_ok_for(
        objectives, resolved.instruments,
        pointing_accuracy_deg=pointing, instrument_by_measurement=assigned,
    )  # fmt: skip

    ctx = AnalysisContext(
        limits=limits,
        mass=mass,
        maneuvers=budget,
        avg_power_w=pw.avg_w,
        peak_power_w=pw.peak_w,
        supply_power_w=pw.supply_w,
        energy=pw.ledger,
        data=ledger,
        buffer_capacity_bits=_p(resolved.cdh, "storage", "bit"),
        contact_links=links,
        science=science,
        science_missing=tuple(sorted(missing.items())),
        cost=cost_estimate(resolved, ops.mission_duration_days, scenario.cost_params),
        reliability=reliability(resolved),
        thermal=thermal_check(resolved, scenario.thermal_exposure),
        compat_issues=compat,
        trajectory_valid=_trajectory_valid(state.trajectory),
        required_measurement_ids=tuple(
            r.id for o in objectives for r in o.required_measurements if r.required
        ),
        pointing_ok=pointing_ok,
        power_ok=power_ok,
    )
    assumptions = _merge(
        ORCHESTRATOR_ASSUMPTIONS,
        scenario.assumptions,
        mass.assumptions,
        budget.assumptions,
        pw.ledger.assumptions,
        comms_mod.ASSUMPTIONS,
        ledger.assumptions,
        science_assumptions(),
        ctx.cost.assumptions,
        RELIABILITY_ASSUMPTIONS,
        THERMAL_ASSUMPTIONS,
        CONSTRAINT_ASSUMPTIONS,
        SCORE_ASSUMPTIONS,
    )
    return _Built(ctx=ctx, maneuvers=budget, propellant_kg=propellant, assumptions=assumptions)


def build_context(
    state: MissionState, catalog: Catalog, *, scenario: ScenarioInputs
) -> AnalysisContext:
    """The AnalysisContext the constraints and score read (exposed for tests and tools)."""
    return _build(state, catalog, scenario).ctx


def _merge(*groups: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(s for g in groups for s in g))


def _versioned(prov: Provenance, model_id: str) -> Provenance:
    return Provenance.model_validate({**prov.model_dump(), "source_version": model_id})


def _q(value: float, unit: Unit, prov: Provenance, unc: Uncertainty | None = None) -> Quantity:
    return Quantity(value=value, unit=unit, provenance=prov, uncertainty=unc)


def _budgets(b: _Built) -> BudgetAnalysis:
    ctx = b.ctx
    m = ctx.mass
    mp = _versioned(m.provenance, m.model_id)
    ep = _versioned(ctx.energy.provenance, ctx.energy.model_id)
    dp = _versioned(ctx.data.provenance, ctx.data.model_id)
    pp = _versioned(b.maneuvers.provenance, b.maneuvers.model_id)
    cp = _versioned(ctx.cost.provenance, ctx.cost.model_id)
    mv = b.maneuvers
    return BudgetAnalysis(
        dry_mass_kg=_q(m.dry_kg, "kg", mp),
        propellant_mass_kg=_q(b.propellant_kg, "kg", mp),
        wet_mass_kg=_q(m.wet_kg, "kg", mp),
        mass_margin_fraction=m.margin_to_limit_fraction,
        average_power_w=_q(ctx.avg_power_w, "W", ep),
        peak_power_w=_q(ctx.peak_power_w, "W", ep),
        energy_margin_fraction=energy_margin_fraction(ctx),
        data_generated_bits=_q(ctx.data.generated_bits, "bit", dp),
        data_downlinked_bits=_q(ctx.data.downlinked_bits, "bit", dp),
        data_margin_fraction=data_return_margin_fraction(ctx),
        required_delta_v_km_per_s=_q(ms_to_kms(mv.required_ms), "km/s", pp),
        available_delta_v_km_per_s=_q(ms_to_kms(mv.available_ms), "km/s", pp),
        delta_v_margin_km_per_s=ms_to_kms(mv.margin_ms),
        estimated_cost_usd=_q(
            ctx.cost.total,
            "USD",
            cp,
            Uncertainty(distribution="interval", min=ctx.cost.low, max=ctx.cost.high),
        ),  # fmt: skip
    )


# --- failure result -------------------------------------------------------------------

_NOT_MODELLED = Provenance(
    fidelity="not-modelled",
    source_name="MISSIONFORGE analysis",
    source_version=MODEL_ID,
    assumptions=("Analysis could not run; placeholder value, not a result.",),
)


def _placeholder_budgets() -> BudgetAnalysis:
    def z(unit: Unit) -> Quantity:
        return _q(0.0, unit, _NOT_MODELLED)

    return BudgetAnalysis(
        dry_mass_kg=z("kg"), propellant_mass_kg=z("kg"), wet_mass_kg=z("kg"),
        mass_margin_fraction=None, average_power_w=z("W"), peak_power_w=z("W"),
        energy_margin_fraction=None, data_generated_bits=z("bit"), data_downlinked_bits=z("bit"),
        data_margin_fraction=None, required_delta_v_km_per_s=z("km/s"),
        available_delta_v_km_per_s=z("km/s"), delta_v_margin_km_per_s=None,
        estimated_cost_usd=z("USD"),
    )  # fmt: skip


def _failed(
    state: MissionState,
    catalog: Catalog,
    exc: DomainValidationError,
    *,
    engine_version: str,
    now: datetime,
) -> MissionAnalysis:
    not_found = isinstance(exc, CatalogItemNotFound)
    cid = "catalog-item-not-found" if not_found else "model-input-invalid"
    label = "Catalogue item not found" if not_found else "Model input invalid"
    action = (
        SuggestedAction(
            action_id="select-catalog-component",
            label=f"Select an existing catalogue component for {exc.field}",
            expected_effect="Lets the engineering analysis run.",
        )
        if not_found
        else SuggestedAction(
            action_id="fix-model-input",
            label=f"Correct {exc.field}",
            expected_effect="Lets the engineering analysis run.",
        )
    )
    constraint = ConstraintResult(
        id=cid,
        label=label,
        status="fail",
        severity=3,
        explanation=f"Analysis could not run: {exc.code} at {exc.field}: {exc.message}.",
        impacted_subsystems=["architecture"],
        suggested_actions=[action],
    )
    why = f"not computed: analysis failed ({exc.code})."
    constraints = [constraint]
    return MissionAnalysis(
        mission_id=state.mission_id,
        design_revision=state.design_revision,
        engine_version=engine_version,
        catalog_version=catalog.version,
        calculated_at=now,
        budgets=_placeholder_budgets(),
        science=ScienceAnalysis(
            coverage_score=0.0,
            weighted_objective_coverage={},
            missing_requirements=[],
            collected_fraction=0.0,
            returned_fraction=0.0,
        ),
        reliability=ReliabilityAnalysis(
            nominal_reliability=0.0, risk_index=0.0, single_point_failures=[]
        ),
        constraints=constraints,
        feasibility=feasibility(constraints),
        mission_ready=mission_ready(constraints),
        score=ScoreBreakdown(
            total=0.0,
            dimensions=tuple(
                ScoreDimension(id=d, weight=w, score=0.0, explanation=why) for d, w in WEIGHTS
            ),
        ),
        top_drivers=top_drivers(constraints),
        assumptions=list(_NOT_MODELLED.assumptions),
    )


# --- entry point ---------------------------------------------------------------------


def _complete(
    state: MissionState,
    catalog: Catalog,
    built: _Built,
    constraints: Sequence[ConstraintResult],
    *,
    engine_version: str,
    now: datetime,
) -> MissionAnalysis:
    ctx = built.ctx
    return MissionAnalysis(
        mission_id=state.mission_id,
        design_revision=state.design_revision,
        engine_version=engine_version,
        catalog_version=catalog.version,
        calculated_at=now,
        budgets=_budgets(built),
        science=ctx.science,
        reliability=ctx.reliability,
        constraints=list(constraints),
        feasibility=feasibility(constraints),
        mission_ready=mission_ready(constraints),
        score=score_preview(ctx, constraints),
        top_drivers=top_drivers(constraints),
        assumptions=list(built.assumptions),
    )


def analyze_mission(
    state: MissionState,
    catalog: Catalog,
    *,
    scenario: ScenarioInputs,
    engine_version: str,
    now: datetime,
) -> MissionAnalysis:
    """Full deterministic engineering analysis of one design revision."""
    try:
        built = _build(state, catalog, scenario)
        constraints = evaluate_constraints(built.ctx)
        return _complete(state, catalog, built, constraints, engine_version=engine_version, now=now)
    except DomainValidationError as exc:
        return _failed(state, catalog, exc, engine_version=engine_version, now=now)
    except ValidationError as exc:  # a contract model rejected an engine value
        err = exc.errors()[0] if exc.error_count() else {"loc": (), "msg": str(exc)}
        loc = ".".join(str(x) for x in err["loc"]) or exc.title
        wrapped = DomainValidationError("MODEL_INPUT_INVALID", loc, str(err["msg"]))
        return _failed(state, catalog, wrapped, engine_version=engine_version, now=now)


__all__ = [
    "ENGINE_VERSION",
    "ORCHESTRATOR_ASSUMPTIONS",
    "SCENARIO_DEFAULTS",
    "ScenarioDefaults",
    "ScenarioInputs",
    "analyze_mission",
    "build_context",
    "scenario_inputs_from_template",
]

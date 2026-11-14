"""Build the typed mission dependency graph (architecture 19.1).

Edge direction convention: ``from_id`` influences ``to_id``. Science flows
instrument -> requirement -> objective; resources flow from the consumer to the subsystem
that supplies or bounds it (instrument -> power, instrument -> C&DH, bus -> launch).
So "upstream" of a node is what it depends on and "downstream" is what it affects.

Node ids are derived only from canonical entity ids (or list positions for plan items),
so an unchanged MissionState always yields the same ids. Pure: no I/O, no clock.
"""

from collections.abc import Iterable, Sequence

from app.domain.catalog.loader import Catalog
from app.schemas.analysis import ConstraintResult, MissionAnalysis
from app.schemas.catalog import CatalogComponent
from app.schemas.mission import MissionState
from app.schemas.optimization import (
    ArchitectureEdge,
    ArchitectureEdgeKind,
    ArchitectureGraph,
    ArchitectureNode,
    ArchitectureNodeKind,
)
from app.schemas.units import Scalar

CONSTRAINT_ATTR_PREFIX = "constraint."

# (category, MissionState architecture field, node label) in display order.
_SUBSYSTEMS: tuple[tuple[str, str, str], ...] = (
    ("bus", "bus_id", "Spacecraft bus (structure and mass)"),
    ("propulsion", "propulsion_id", "Propulsion"),
    ("power", "power_id", "Power (array and battery)"),
    ("adcs", "adcs_id", "Attitude control and pointing"),
    ("communications", "communications_id", "Communications radio"),
    ("thermal", "thermal_id", "Thermal control"),
    ("cdh", "cdh_id", "Command and data handling (storage)"),
)

# Constraint `impacted_subsystems` tags -> graph node ids (instrument/objective tags expand).
_TAG_TO_SUBSYSTEM: dict[str, str] = {
    "mass": "subsystem:bus",
    "bus": "subsystem:bus",
    "propulsion": "subsystem:propulsion",
    "power": "subsystem:power",
    "adcs": "subsystem:adcs",
    "communications": "subsystem:communications",
    "thermal": "subsystem:thermal",
    "data": "subsystem:cdh",
    "cdh": "subsystem:cdh",
}

# Owner nodes per constraint id (the engine only lists subsystem tags on warn/fail
# results, so passing verdicts are placed by id). "objectives" expands to every objective.
_CONSTRAINT_OWNERS: dict[str, tuple[str, ...]] = {
    "mass-launch-limit": ("launch", "subsystem:bus"),
    "mass-margin": ("subsystem:bus",),
    "delta-v-margin": ("subsystem:propulsion", "trajectory"),
    "peak-power": ("subsystem:power",),
    "energy-closure": ("subsystem:power",),
    "battery-reserve": ("subsystem:power",),
    "data-buffer": ("subsystem:cdh",),
    "link-margin": ("subsystem:communications",),
    "data-return": ("subsystem:communications", "subsystem:cdh"),
    "science-mandatory-coverage": ("objectives",),
    "science-minimum-score": ("objectives",),
    "trajectory-valid": ("trajectory",),
    "thermal": ("subsystem:thermal",),
}

_STATUS_RANK: dict[str, int] = {"pass": 0, "not-modelled": 0, "warning": 1, "fail": 2}


class _Builder:
    def __init__(self) -> None:
        self.nodes: dict[str, ArchitectureNode] = {}
        self.edges: dict[str, ArchitectureEdge] = {}

    def node(
        self,
        node_id: str,
        kind: ArchitectureNodeKind,
        label: str,
        entity_id: str | None,
        attributes: dict[str, Scalar],
    ) -> None:
        if node_id in self.nodes:  # duplicate entity (e.g. repeated instrument id): keep first
            return
        self.nodes[node_id] = ArchitectureNode(
            id=node_id, kind=kind, label=label, entity_id=entity_id, attributes=attributes
        )

    def edge(self, from_id: str, to_id: str, kind: ArchitectureEdgeKind, rationale: str) -> None:
        if from_id not in self.nodes or to_id not in self.nodes:
            return
        edge_id = f"{kind}:{from_id}->{to_id}"
        if edge_id in self.edges:
            return
        self.edges[edge_id] = ArchitectureEdge(
            id=edge_id, from_id=from_id, to_id=to_id, kind=kind, rationale=rationale
        )

    def graph(self) -> ArchitectureGraph:
        return ArchitectureGraph(nodes=list(self.nodes.values()), edges=list(self.edges.values()))


def _param(component: CatalogComponent | None, key: str) -> float | None:
    if component is None:
        return None
    quantity = component.parameters.get(key)
    return None if quantity is None else float(quantity.value)


def _fmt(value: float) -> str:
    return f"{value:.4g}"


def _attrs(**values: Scalar | None) -> dict[str, Scalar]:
    return {key: value for key, value in values.items() if value is not None}


def _instrument_nodes(
    b: _Builder, state: MissionState, catalog: Catalog
) -> list[tuple[str, CatalogComponent | None]]:
    """One node per distinct instrument id (quantity = how often it is listed)."""
    counts: dict[str, int] = {}
    for cid in state.architecture.instrument_ids:
        counts[cid] = counts.get(cid, 0) + 1
    result: list[tuple[str, CatalogComponent | None]] = []
    for cid, count in counts.items():
        comp = catalog.get(cid)
        node_id = f"instrument:{cid}"
        b.node(
            node_id,
            "instrument",
            comp.name if comp else cid,
            cid,
            _attrs(
                quantity=count,
                capabilities=", ".join(comp.capabilities) if comp else "",
                massKg=_param(comp, "mass"),
                powerW=_param(comp, "power_w"),
                dataRateBitsPerSecond=_param(comp, "data_rate"),
                pointingRequirementDeg=_param(comp, "pointing_requirement"),
                inCatalog=comp is not None,
            ),
        )
        result.append((node_id, comp))
    return result


def _subsystem_attrs(
    category: str, comp: CatalogComponent | None, a: MissionAnalysis
) -> dict[str, Scalar]:
    budgets = a.budgets
    if category == "bus":
        return _attrs(
            componentMassKg=_param(comp, "mass"),
            dryMassKg=budgets.dry_mass_kg.value,
            wetMassKg=budgets.wet_mass_kg.value,
            massMarginFraction=budgets.mass_margin_fraction,
        )
    if category == "propulsion":
        return _attrs(
            ispS=_param(comp, "isp"),
            propellantMassKg=budgets.propellant_mass_kg.value,
            requiredDeltaVKmPerS=budgets.required_delta_v_km_per_s.value,
            availableDeltaVKmPerS=budgets.available_delta_v_km_per_s.value,
            deltaVMarginKmPerS=budgets.delta_v_margin_km_per_s,
        )
    if category == "power":
        return _attrs(
            arrayPowerAt1AuW=_param(comp, "array_power_at_1au"),
            batteryCapacityWh=_param(comp, "battery_capacity"),
            averagePowerW=budgets.average_power_w.value,
            peakPowerW=budgets.peak_power_w.value,
            energyMarginFraction=budgets.energy_margin_fraction,
        )
    if category == "adcs":
        return _attrs(pointingAccuracyDeg=_param(comp, "pointing_accuracy"))
    if category == "communications":
        return _attrs(
            antennaGainDbi=_param(comp, "antenna_gain"),
            maxDataRateBitsPerSecond=_param(comp, "max_data_rate"),
            dataDownlinkedBits=budgets.data_downlinked_bits.value,
        )
    if category == "cdh":
        return _attrs(
            storageBits=_param(comp, "storage"),
            dataGeneratedBits=budgets.data_generated_bits.value,
            dataDownlinkedBits=budgets.data_downlinked_bits.value,
            dataMarginFraction=budgets.data_margin_fraction,
        )
    return _attrs(powerW=_param(comp, "power_w"))


def _science(
    b: _Builder,
    state: MissionState,
    analysis: MissionAnalysis,
    instruments: Sequence[tuple[str, CatalogComponent | None]],
) -> None:
    missing = set(analysis.science.missing_requirements)
    coverage = analysis.science.weighted_objective_coverage
    for obj in state.science_objectives:
        statuses: list[str] = []
        for req in obj.required_measurements:
            providers = [
                nid
                for nid, comp in instruments
                if comp and req.instrument_capability in comp.capabilities
            ]
            if not providers:
                status = "uncovered"
            elif req.id in missing:
                status = "not-returned"
            else:
                status = "covered"
            if req.required:
                statuses.append(status)
            b.node(
                f"requirement:{req.id}",
                "measurement-requirement",
                req.description,
                req.id,
                _attrs(
                    capability=req.instrument_capability,
                    required=req.required,
                    coverageWeight=req.coverage_weight,
                    status=status,
                ),
            )
        covered = sum(s == "covered" for s in statuses)
        if not statuses:
            obj_status = "covered"
        elif covered == len(statuses):
            obj_status = "covered"
        elif any(s != "uncovered" for s in statuses):
            obj_status = "partial"
        else:
            obj_status = "uncovered"
        b.node(
            f"objective:{obj.id}",
            "science-objective",
            obj.title,
            obj.id,
            _attrs(priority=obj.priority, coverage=coverage.get(obj.id), status=obj_status),
        )
        for req in obj.required_measurements:
            b.edge(
                f"requirement:{req.id}",
                f"objective:{obj.id}",
                "satisfies",
                f"Measurement contributes coverage weight {_fmt(req.coverage_weight)} "
                f"to objective '{obj.title}'"
                + (" (required)." if req.required else " (optional)."),
            )
            for nid, comp in instruments:
                if comp and req.instrument_capability in comp.capabilities:
                    b.edge(
                        nid,
                        f"requirement:{req.id}",
                        "satisfies",
                        f"{comp.name} provides the '{req.instrument_capability}' capability "
                        "this measurement needs.",
                    )


def _resources(
    b: _Builder,
    state: MissionState,
    catalog: Catalog,
    instruments: Sequence[tuple[str, CatalogComponent | None]],
    analysis: MissionAnalysis,
) -> None:
    arch = state.architecture
    for category, field, label in _SUBSYSTEMS:
        cid = str(getattr(arch, field))
        comp = catalog.get(cid)
        b.node(
            f"subsystem:{category}",
            "spacecraft-subsystem",
            f"{label}: {comp.name if comp else cid}",
            cid,
            {"category": category, **_subsystem_attrs(category, comp, analysis)},
        )
    launch = catalog.get(arch.launch_vehicle_id)
    b.node(
        "launch",
        "launch-option",
        launch.name if launch else arch.launch_vehicle_id,
        arch.launch_vehicle_id,
        _attrs(
            launchMassLimitKg=_param(launch, "launch_mass_limit"),
            wetMassKg=analysis.budgets.wet_mass_kg.value,
            estimatedCostUsd=analysis.budgets.estimated_cost_usd.value,
        ),
    )
    traj = state.trajectory
    b.node(
        "trajectory",
        "trajectory-option",
        f"Trajectory {traj.option_id} ({traj.provider})",
        traj.option_id,
        _attrs(
            provider=traj.provider,
            c3KmSquaredPerSSquared=traj.c3_km2_per_s2,
            missionDeltaVKmPerS=traj.mission_delta_v_km_per_s,
            timeOfFlightDays=traj.time_of_flight_days,
        ),
    )

    for nid, comp in instruments:
        name = comp.name if comp else nid
        power = _param(comp, "power_w")
        rate = _param(comp, "data_rate")
        pointing = _param(comp, "pointing_requirement")
        mass = _param(comp, "mass")
        b.edge(
            nid, "subsystem:power", "consumes",
            f"{name} draws {_fmt(power)} W while observing." if power is not None
            else f"{name} draws power while observing.",
        )  # fmt: skip
        b.edge(
            nid, "subsystem:cdh", "generates",
            f"{name} produces {_fmt(rate)} bit/s that must be stored until a contact."
            if rate is not None else f"{name} produces data that must be stored.",
        )  # fmt: skip
        b.edge(
            nid, "subsystem:adcs", "depends-on",
            f"{name} needs pointing better than {_fmt(pointing)} deg." if pointing is not None
            else f"{name} needs the spacecraft pointed at the target.",
        )  # fmt: skip
        b.edge(
            nid, "subsystem:thermal", "depends-on",
            f"{name} heat load is handled by thermal control.",
        )  # fmt: skip
        b.edge(
            nid, "subsystem:bus", "allocated-to",
            f"{name} adds {_fmt(mass)} kg to the spacecraft." if mass is not None
            else f"{name} adds mass to the spacecraft.",
        )  # fmt: skip

    for category in ("propulsion", "adcs", "communications", "thermal", "cdh"):
        sid = f"subsystem:{category}"
        b.edge(sid, "subsystem:power", "consumes", f"{category} hardware draws spacecraft power.")
    for category in ("propulsion", "power", "adcs", "communications", "thermal", "cdh"):
        b.edge(
            f"subsystem:{category}", "subsystem:bus", "allocated-to",
            f"{category} hardware mass is carried by the bus.",
        )  # fmt: skip
    b.edge(
        "subsystem:cdh", "subsystem:communications", "downlinks-through",
        "Stored data can only leave the spacecraft through the radio.",
    )  # fmt: skip
    b.edge(
        "subsystem:bus", "launch", "depends-on",
        "The wet spacecraft mass must fit within the launch vehicle mass limit.",
    )  # fmt: skip
    b.edge(
        "trajectory", "subsystem:propulsion", "constrains",
        "The trajectory sets the delta-v the propulsion system must deliver.",
    )  # fmt: skip
    b.edge(
        "trajectory", "launch", "constrains",
        "The trajectory sets the departure energy (C3) the launch must provide.",
    )  # fmt: skip


def _operations(
    b: _Builder,
    state: MissionState,
    analysis: MissionAnalysis,
    instruments: Sequence[tuple[str, CatalogComponent | None]],
) -> None:
    ops = state.operations
    capability_of = {
        req.id: (req.instrument_capability, obj.id)
        for obj in state.science_objectives
        for req in obj.required_measurements
    }
    contacts: list[tuple[str, float]] = []
    for i, contact_item in enumerate(ops.downlink_plan):
        cid = f"contact:{i}"
        b.node(
            cid,
            "contact-window",
            f"Contact day {_fmt(contact_item.start_day)} "
            f"({_fmt(contact_item.duration_minutes)} min)",
            None,
            _attrs(
                startDay=contact_item.start_day,
                durationMinutes=contact_item.duration_minutes,
                plannedDataRateBitsPerSecond=contact_item.data_rate_bits_per_second,
                groundSegmentId=state.architecture.ground_segment_id,
            ),
        )
        b.edge(
            "subsystem:communications", cid, "downlinks-through",
            "The radio returns stored data to Earth during this contact.",
        )  # fmt: skip
        contacts.append((cid, contact_item.start_day))

    def next_contact(after_day: float) -> str | None:
        later = [c for c in contacts if c[1] >= after_day]
        return min(later, key=lambda c: (c[1], c[0]))[0] if later else None

    first_obs_day: dict[str, float] = {}
    for i, item in enumerate(ops.observation_plan):
        oid = f"observation:{i}"
        end_day = item.start_day + item.duration_hours / 24.0
        b.node(
            oid,
            "observation-task",
            f"Observe {item.measurement_id} from day {_fmt(item.start_day)}",
            item.measurement_id,
            _attrs(
                measurementId=item.measurement_id,
                startDay=item.start_day,
                durationHours=item.duration_hours,
                dutyCycle=item.duty_cycle,
            ),
        )
        b.edge(
            oid, f"requirement:{item.measurement_id}", "satisfies",
            "Scheduled observing time counts toward this measurement's required time.",
        )  # fmt: skip
        capability = capability_of.get(item.measurement_id, ("", ""))[0]
        for nid, comp in instruments:
            if comp and capability and capability in comp.capabilities:
                b.edge(oid, nid, "allocated-to", f"Observation is performed by {comp.name}.")
        contact = next_contact(end_day)
        if contact is not None:
            b.edge(
                oid, contact, "downlinks-through",
                "First planned contact after this observation ends.",
            )  # fmt: skip
        if item.measurement_id not in first_obs_day:
            first_obs_day[item.measurement_id] = end_day

    for meas_id, end_day in first_obs_day.items():
        pid = f"product:{meas_id}"
        b.node(
            pid,
            "science-product",
            f"Science data: {meas_id}",
            meas_id,
            _attrs(
                collectedFraction=analysis.science.collected_fraction,
                returnedFraction=analysis.science.returned_fraction,
            ),
        )
        for i, item in enumerate(ops.observation_plan):
            if item.measurement_id == meas_id:
                b.edge(
                    f"observation:{i}", pid, "generates", "Observation produces this science data."
                )
        contact = next_contact(end_day)
        if contact is not None:
            b.edge(pid, contact, "downlinks-through", "Data is first returned at this contact.")
        obj_id = capability_of.get(meas_id, ("", ""))[1]
        if obj_id:
            b.edge(pid, f"objective:{obj_id}", "satisfies", "Returned data answers this objective.")


def _constraint_owners(
    constraint: ConstraintResult,
    b: _Builder,
    instruments: Sequence[tuple[str, CatalogComponent | None]],
) -> list[str]:
    objectives = [nid for nid, n in b.nodes.items() if n.kind == "science-objective"]
    owners: list[str] = []
    for owner in _CONSTRAINT_OWNERS.get(constraint.id, ()):
        owners.extend(objectives if owner == "objectives" else [owner])
    for tag in constraint.impacted_subsystems:
        if tag in _TAG_TO_SUBSYSTEM:
            owners.append(_TAG_TO_SUBSYSTEM[tag])
        elif tag in ("launch", "trajectory"):
            owners.append(tag)
        elif tag == "payload":
            owners.extend(nid for nid, _ in instruments)
        elif tag == "science":
            owners.extend(objectives)
        else:  # a component id (compat-* constraints)
            owners.extend(nid for nid, n in b.nodes.items() if n.entity_id == tag)
    unique: dict[str, None] = {}
    for owner in owners:
        if owner in b.nodes:
            unique.setdefault(owner)
    return list(unique)


def _attach_constraints(
    b: _Builder,
    constraints: Iterable[ConstraintResult],
    instruments: Sequence[tuple[str, CatalogComponent | None]],
) -> None:
    for c in constraints:
        for owner in _constraint_owners(c, b, instruments):
            node = b.nodes[owner]
            key = f"{CONSTRAINT_ATTR_PREFIX}{c.id}"
            previous = node.attributes.get(key)
            # Two results with one id (unlikely) keep the worse status.
            new_rank = _STATUS_RANK[c.status]
            if isinstance(previous, str) and _STATUS_RANK.get(previous, 0) >= new_rank:
                continue
            attributes = {**node.attributes, key: c.status}
            b.nodes[owner] = node.model_copy(update={"attributes": attributes})


def build_architecture_graph(
    state: MissionState, analysis: MissionAnalysis, catalog: Catalog
) -> ArchitectureGraph:
    """Typed directed graph of one design revision. Does not mutate its inputs."""
    b = _Builder()
    instruments = _instrument_nodes(b, state, catalog)
    _science(b, state, analysis, instruments)
    _resources(b, state, catalog, instruments, analysis)
    _operations(b, state, analysis, instruments)
    _attach_constraints(b, analysis.constraints, instruments)
    return b.graph()

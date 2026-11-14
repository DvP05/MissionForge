"""Deterministic science-to-engineering traceability graph."""

from collections.abc import Mapping

from app.domain.catalog.loader import Catalog
from app.schemas.analysis import MissionAnalysis
from app.schemas.mission import MissionState
from app.schemas.optimization import ArchitectureEdge, ArchitectureGraph, ArchitectureNode


def _node(kind: str, entity_id: str, label: str, **attributes: object) -> ArchitectureNode:
    return ArchitectureNode(
        id=f"{kind}:{entity_id}",
        kind=kind,
        label=label,
        entity_id=entity_id,
        attributes={k: v for k, v in attributes.items() if isinstance(v, (str, bool, int, float))},
    )


def build_traceability_graph(
    state: MissionState,
    analysis: MissionAnalysis,
    catalog: Mapping[str, object] | Catalog,
) -> ArchitectureGraph:
    """Build a stable graph without mutating state or calculating engineering metrics."""
    nodes: dict[str, ArchitectureNode] = {}
    edges: list[ArchitectureEdge] = []

    def add(node: ArchitectureNode) -> None:
        nodes.setdefault(node.id, node)

    def link(kind: str, from_id: str, to_id: str, rationale: str) -> None:
        edges.append(
            ArchitectureEdge(
                id=f"{kind}:{from_id}->{to_id}",
                from_id=from_id,
                to_id=to_id,
                kind=kind,
                rationale=rationale,
            )
        )

    for objective in state.science_objectives:
        objective_id = f"science-objective:{objective.id}"
        add(_node("science-objective", objective.id, objective.title))
        for requirement in objective.required_measurements:
            requirement_id = f"measurement-requirement:{requirement.id}"
            add(
                _node(
                    "measurement-requirement",
                    requirement.id,
                    requirement.description,
                    required=requirement.required,
                )
            )
            link(
                "satisfies",
                objective_id,
                requirement_id,
                "The objective requires this measurement.",
            )
            instrument_ids = [
                instrument_id
                for instrument_id in state.architecture.instrument_ids
                if instrument_id in catalog
                and requirement.instrument_capability
                in getattr(catalog[instrument_id], "capabilities", [])
            ]
            for instrument_id in instrument_ids:
                add(
                    _node(
                        "instrument",
                        instrument_id,
                        getattr(catalog[instrument_id], "name", instrument_id),
                    )
                )
                link(
                    "allocated-to",
                    requirement_id,
                    f"instrument:{instrument_id}",
                    f"Instrument capability includes {requirement.instrument_capability}.",
                )

    architecture_fields = (
        "launch_vehicle_id", "bus_id", "propulsion_id", "power_id", "adcs_id",
        "communications_id", "thermal_id", "cdh_id", "ground_segment_id",
    )
    for field in architecture_fields:
        component_id = str(getattr(state.architecture, field))
        add(_node("spacecraft-subsystem", component_id, component_id, category=field))

    metric_values = {
        "dry-mass": analysis.budgets.dry_mass_kg.value,
        "average-power": analysis.budgets.average_power_w.value,
        "data-generated": analysis.budgets.data_generated_bits.value,
        "delta-v-margin": analysis.budgets.delta_v_margin_km_per_s,
        "science-coverage": analysis.science.coverage_score,
    }
    for metric_id, value in metric_values.items():
        add(_node("science-product", metric_id, metric_id.replace("-", " ").title(), value=value))

    for constraint in analysis.constraints:
        add(_node("science-product", constraint.id, constraint.label, status=constraint.status))
        for subsystem in constraint.impacted_subsystems:
            subsystem_id = f"spacecraft-subsystem:{subsystem}"
            if subsystem_id in nodes:
                link(
                    "constrains",
                    subsystem_id,
                    f"science-product:{constraint.id}",
                    constraint.explanation,
                )

    for objective in state.science_objectives:
        for requirement in objective.required_measurements:
            requirement_id = f"measurement-requirement:{requirement.id}"
            for metric_id in metric_values:
                link(
                    "generates",
                    requirement_id,
                    f"science-product:{metric_id}",
                    "The analysis reports the derived mission metric.",
                )

    return ArchitectureGraph(nodes=list(nodes.values()), edges=edges)

"""Science (STM) and mission (MTM) traceability matrices, projected from the graph.

Both tables are read from the same ArchitectureGraph the explorer shows, so the views
can never disagree with each other (architecture 19.1: projections of one canonical state).
"""

from dataclasses import dataclass

from app.schemas.optimization import ArchitectureGraph, ArchitectureNode


@dataclass(frozen=True)
class ScienceTraceRow:
    """STM row: objective -> measurement requirement -> instruments that provide it."""

    objective_id: str
    objective_title: str
    requirement_id: str
    requirement_description: str
    capability: str
    required: bool
    instrument_ids: tuple[str, ...]
    observation_count: int
    status: str  # covered | not-returned | uncovered


@dataclass(frozen=True)
class MissionTraceRow:
    """MTM row: instrument -> requirements it serves and the subsystems it loads."""

    instrument_id: str
    instrument_name: str
    requirement_ids: tuple[str, ...]
    subsystem_ids: tuple[str, ...]  # catalogue ids of power/C&DH/ADCS/thermal/bus it loads
    observation_count: int


def _text(node: ArchitectureNode, key: str) -> str:
    value = node.attributes.get(key)
    return value if isinstance(value, str) else ""


def build_traceability_matrices(
    graph: ArchitectureGraph,
) -> tuple[list[ScienceTraceRow], list[MissionTraceRow]]:
    nodes = {n.id: n for n in graph.nodes}
    outgoing: dict[str, list[tuple[str, str]]] = {n.id: [] for n in graph.nodes}
    incoming: dict[str, list[tuple[str, str]]] = {n.id: [] for n in graph.nodes}
    for e in graph.edges:
        outgoing[e.from_id].append((e.kind, e.to_id))
        incoming[e.to_id].append((e.kind, e.from_id))

    def kind_of(node_id: str) -> str:
        return nodes[node_id].kind

    stm: list[ScienceTraceRow] = []
    for obj in (n for n in graph.nodes if n.kind == "science-objective"):
        for kind, req_id in incoming[obj.id]:
            if kind != "satisfies" or kind_of(req_id) != "measurement-requirement":
                continue
            req = nodes[req_id]
            sources = [src for k, src in incoming[req_id] if k == "satisfies"]
            stm.append(
                ScienceTraceRow(
                    objective_id=obj.entity_id or obj.id,
                    objective_title=obj.label,
                    requirement_id=req.entity_id or req.id,
                    requirement_description=req.label,
                    capability=_text(req, "capability"),
                    required=req.attributes.get("required") is True,
                    instrument_ids=tuple(
                        nodes[s].entity_id or s for s in sources if kind_of(s) == "instrument"
                    ),
                    observation_count=sum(kind_of(s) == "observation-task" for s in sources),
                    status=_text(req, "status"),
                )
            )

    mtm: list[MissionTraceRow] = []
    for inst in (n for n in graph.nodes if n.kind == "instrument"):
        reqs = [dst for k, dst in outgoing[inst.id] if k == "satisfies"]
        subsystems = [dst for _, dst in outgoing[inst.id] if kind_of(dst) == "spacecraft-subsystem"]
        mtm.append(
            MissionTraceRow(
                instrument_id=inst.entity_id or inst.id,
                instrument_name=inst.label,
                requirement_ids=tuple(nodes[r].entity_id or r for r in reqs),
                subsystem_ids=tuple(nodes[s].entity_id or s for s in subsystems),
                observation_count=sum(
                    k == "allocated-to" and kind_of(src) == "observation-task"
                    for k, src in incoming[inst.id]
                ),
            )
        )
    return stm, mtm

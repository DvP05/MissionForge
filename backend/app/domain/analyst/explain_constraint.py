"""Plain-language "because" chain for one constraint (architecture 19.1 / 19.8)."""

from app.domain.architecture_graph.traversal import nodes_for_constraint
from app.schemas.analysis import MissionAnalysis
from app.schemas.optimization import ArchitectureGraph


def explain_constraint(
    analysis: MissionAnalysis, graph: ArchitectureGraph, constraint_id: str
) -> list[str]:
    """Lines: the verdict, where it is checked, and what feeds those parts (with reasons)."""
    result = next((c for c in analysis.constraints if c.id == constraint_id), None)
    if result is None:
        return []
    labels = {n.id: n.label for n in graph.nodes}
    lines = [f"{result.label} is {result.status}: {result.explanation}"]
    owners = nodes_for_constraint(graph, constraint_id)
    if owners:
        lines.append("Checked on: " + ", ".join(labels[o] for o in owners) + ".")
    seen: set[str] = set()
    for e in graph.edges:
        if e.to_id in owners and e.from_id not in owners and e.id not in seen:
            seen.add(e.id)
            lines.append(f"Because {labels[e.from_id]} -> {labels[e.to_id]}: {e.rationale}")
    for action in result.suggested_actions:
        lines.append(f"Try: {action.label} ({action.expected_effect})")
    return lines

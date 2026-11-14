"""Small pure traversal helpers over an ArchitectureGraph (no graph database, 19.1)."""

from collections import deque

from app.schemas.optimization import ArchitectureGraph

_CONSTRAINT_PREFIX = "constraint."


def _adjacency(graph: ArchitectureGraph, *, reverse: bool) -> dict[str, list[str]]:
    adj: dict[str, list[str]] = {n.id: [] for n in graph.nodes}
    for e in graph.edges:
        src, dst = (e.to_id, e.from_id) if reverse else (e.from_id, e.to_id)
        adj[src].append(dst)
    return adj


def _reach(graph: ArchitectureGraph, start: str, *, reverse: bool) -> list[str]:
    if start not in {n.id for n in graph.nodes}:
        raise KeyError(start)
    adj = _adjacency(graph, reverse=reverse)
    seen = {start}
    order: list[str] = []
    queue = deque([start])
    while queue:
        for nxt in adj[queue.popleft()]:
            if nxt not in seen:
                seen.add(nxt)
                order.append(nxt)
                queue.append(nxt)
    return order


def downstream(graph: ArchitectureGraph, node_id: str) -> list[str]:
    """Nodes this node affects (follows edges forward), breadth-first, excluding itself."""
    return _reach(graph, node_id, reverse=False)


def upstream(graph: ArchitectureGraph, node_id: str) -> list[str]:
    """Nodes this node depends on (follows edges backward), breadth-first, excluding itself."""
    return _reach(graph, node_id, reverse=True)


def find_path(graph: ArchitectureGraph, from_id: str, to_id: str) -> list[str] | None:
    """Shortest forward path of node ids from `from_id` to `to_id`, or None."""
    known = {n.id for n in graph.nodes}
    if from_id not in known or to_id not in known:
        return None
    adj = _adjacency(graph, reverse=False)
    parent: dict[str, str | None] = {from_id: None}
    queue = deque([from_id])
    while queue:
        cur = queue.popleft()
        if cur == to_id:
            path = [cur]
            while (prev := parent[path[-1]]) is not None:
                path.append(prev)
            return path[::-1]
        for nxt in adj[cur]:
            if nxt not in parent:
                parent[nxt] = cur
                queue.append(nxt)
    return None


def nodes_for_constraint(graph: ArchitectureGraph, constraint_id: str) -> list[str]:
    """Ids of nodes that carry the verdict of `constraint_id` as an attribute."""
    key = f"{_CONSTRAINT_PREFIX}{constraint_id}"
    return [n.id for n in graph.nodes if key in n.attributes]

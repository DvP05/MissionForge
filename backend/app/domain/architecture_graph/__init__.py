"""Architecture graph and causal explainability (architecture 19.1, Task 6.1, module M09).

The graph is a read-only projection of a canonical ``MissionState`` plus its
``MissionAnalysis``: it is rebuilt on demand and never edited.

Node kinds are the frozen 19.1 set. Engineering metrics and constraint verdicts are not
separate node kinds there, so they are carried as node attributes on the node that owns
them (for example the C&DH node carries the data budget and the ``data-buffer`` verdict
under ``constraint.data-buffer``). ``nodes_for_constraint`` finds those owners.
"""

from app.domain.architecture_graph.build_architecture_graph import (
    CONSTRAINT_ATTR_PREFIX,
    build_architecture_graph,
)
from app.domain.architecture_graph.build_traceability_matrices import (
    MissionTraceRow,
    ScienceTraceRow,
    build_traceability_matrices,
)
from app.domain.architecture_graph.trace_impact import trace_impact
from app.domain.architecture_graph.traversal import (
    downstream,
    find_path,
    nodes_for_constraint,
    upstream,
)

__all__ = [
    "CONSTRAINT_ATTR_PREFIX",
    "MissionTraceRow",
    "ScienceTraceRow",
    "build_architecture_graph",
    "build_traceability_matrices",
    "downstream",
    "find_path",
    "nodes_for_constraint",
    "trace_impact",
    "upstream",
]

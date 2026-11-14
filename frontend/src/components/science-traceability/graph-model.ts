import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type ArchitectureGraph = Schemas["ArchitectureGraph"];
export type ArchitectureNode = Schemas["ArchitectureNode"];
export type ArchitectureEdge = Schemas["ArchitectureEdge"];
export type ImpactReport = Schemas["ImpactReport"];
export type GraphData = Schemas["GraphData"];
export type ConstraintStatus = Schemas["ConstraintResult"]["status"];
type NodeKind = ArchitectureNode["kind"];

/** Must match CONSTRAINT_ATTR_PREFIX in backend/app/domain/architecture_graph. */
export const CONSTRAINT_PREFIX = "constraint.";

export interface GraphColumn {
  id: string;
  title: string;
  kinds: readonly NodeKind[];
}

/** Display columns, left to right: why we fly -> what we carry -> how it operates. */
export const COLUMNS: readonly GraphColumn[] = [
  { id: "objectives", title: "Science objectives", kinds: ["science-objective"] },
  { id: "requirements", title: "Measurements", kinds: ["measurement-requirement"] },
  { id: "instruments", title: "Instruments", kinds: ["instrument"] },
  {
    id: "spacecraft",
    title: "Spacecraft and launch",
    kinds: ["spacecraft-subsystem", "launch-option", "trajectory-option"],
  },
  {
    id: "operations",
    title: "Operations and returned data",
    kinds: ["observation-task", "science-product", "contact-window"],
  },
];

export const KIND_LABEL: Record<NodeKind, string> = {
  "science-objective": "Science objective",
  "measurement-requirement": "Measurement requirement",
  instrument: "Instrument",
  "spacecraft-subsystem": "Spacecraft subsystem",
  "launch-option": "Launch vehicle",
  "trajectory-option": "Trajectory",
  "observation-task": "Observation task",
  "contact-window": "Ground contact",
  "science-product": "Science data product",
};

export type Relation = "selected" | "affects" | "depends-on" | "unrelated";

/** Breadth-first reachability over the backend's edges (display only, no engineering). */
function reach(graph: ArchitectureGraph, start: string, forward: boolean): Set<string> {
  const adj = new Map<string, string[]>();
  for (const e of graph.edges) {
    const [src, dst] = forward ? [e.fromId, e.toId] : [e.toId, e.fromId];
    const list = adj.get(src);
    if (list) list.push(dst);
    else adj.set(src, [dst]);
  }
  const seen = new Set<string>();
  const queue = [start];
  while (queue.length > 0) {
    const cur = queue.shift() as string;
    for (const next of adj.get(cur) ?? []) {
      if (next !== start && !seen.has(next)) {
        seen.add(next);
        queue.push(next);
      }
    }
  }
  return seen;
}

/** Relation of every node to the selected node. Downstream wins over upstream on cycles. */
export function relations(graph: ArchitectureGraph, selectedId: string | null): Map<string, Relation> {
  const out = new Map<string, Relation>();
  if (!selectedId) return out;
  const down = reach(graph, selectedId, true);
  const up = reach(graph, selectedId, false);
  for (const n of graph.nodes) {
    if (n.id === selectedId) out.set(n.id, "selected");
    else if (down.has(n.id)) out.set(n.id, "affects");
    else if (up.has(n.id)) out.set(n.id, "depends-on");
    else out.set(n.id, "unrelated");
  }
  return out;
}

const RANK: Record<ConstraintStatus, number> = { "not-modelled": 0, pass: 1, warning: 2, fail: 3 };

/** Constraint verdicts the backend attached to this node, worst first. */
export function nodeConstraints(node: ArchitectureNode): { id: string; status: ConstraintStatus }[] {
  const out: { id: string; status: ConstraintStatus }[] = [];
  for (const [key, value] of Object.entries(node.attributes ?? {})) {
    if (key.startsWith(CONSTRAINT_PREFIX) && typeof value === "string" && value in RANK) {
      out.push({ id: key.slice(CONSTRAINT_PREFIX.length), status: value as ConstraintStatus });
    }
  }
  return out.sort((a, b) => RANK[b.status] - RANK[a.status] || a.id.localeCompare(b.id));
}

export function worstStatus(node: ArchitectureNode): ConstraintStatus | null {
  return nodeConstraints(node)[0]?.status ?? null;
}

/** Plain attributes (not constraint verdicts), in backend order. */
export function plainAttributes(node: ArchitectureNode): [string, string | number | boolean][] {
  return Object.entries(node.attributes ?? {}).filter(([key]) => !key.startsWith(CONSTRAINT_PREFIX));
}

/** "dataGeneratedBits" -> "Data generated bits" */
export function labelFromKey(key: string): string {
  const words = key.replace(/([a-z0-9])([A-Z])/g, "$1 $2").toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Human labels for ImpactReport metric ids (backend trace_impact). */
export const METRIC_LABEL: Record<string, string> = {
  dryMassKg: "Dry mass",
  propellantMassKg: "Propellant mass",
  wetMassKg: "Wet mass",
  averagePowerW: "Average power",
  peakPowerW: "Peak power",
  dataGeneratedBits: "Data generated",
  dataDownlinkedBits: "Data returned to Earth",
  requiredDeltaVKmPerS: "Required delta-v",
  availableDeltaVKmPerS: "Available delta-v",
  estimatedCostUsd: "Estimated cost",
  massMarginFraction: "Mass margin",
  energyMarginFraction: "Energy margin",
  dataMarginFraction: "Data margin",
  deltaVMarginKmPerS: "Delta-v margin",
  scienceCoverageScore: "Science coverage score",
  collectedFraction: "Science collected",
  returnedFraction: "Science returned",
  nominalReliability: "Nominal reliability",
  scoreTotal: "Mission score",
};

export const STATUS_TEXT: Record<string, string> = {
  covered: "Covered",
  partial: "Partly covered",
  uncovered: "UNCOVERED",
  "not-returned": "Data not returned",
};

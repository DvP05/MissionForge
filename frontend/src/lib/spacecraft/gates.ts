/**
 * Engineering gates (design_update.md 7.2): backend constraint results grouped into the gates
 * a player clears. A gate's status is its worst constraint; a gate whose constraints are all
 * not modelled is NOT MODELLED, never PASS. Nothing here evaluates engineering itself.
 */
import type { components } from "@/lib/api/schema";
import { constraintCategories, constraintStatus, type EngStatus } from "./engineering-status";
import type { ComponentCategory } from "./part-registry";

type Constraint = components["schemas"]["ConstraintResult"];

export interface GateDef {
  id: string;
  label: string;
  /** Constraint ids (exact) or a prefix ending in "*". */
  constraints: string[];
  /** Where a repair usually starts (catalogue subsystem to open). */
  repair: ComponentCategory;
}

export const GATES: GateDef[] = [
  { id: "science", label: "Science traceability", constraints: ["science-mandatory-coverage", "science-minimum-score"], repair: "instrument" },
  { id: "mass", label: "Launch mass", constraints: ["mass-launch-limit", "mass-margin"], repair: "bus" },
  { id: "power", label: "Power and energy", constraints: ["peak-power", "energy-closure", "battery-reserve"], repair: "power" },
  { id: "propulsion", label: "Propulsion and Δv", constraints: ["delta-v-margin", "trajectory-valid"], repair: "propulsion" },
  { id: "comms", label: "Communications and data return", constraints: ["link-margin", "data-return", "data-buffer"], repair: "communications" },
  { id: "thermal", label: "Thermal", constraints: ["thermal"], repair: "thermal" },
  { id: "budget", label: "Budget", constraints: ["budget"], repair: "bus" },
  { id: "compat", label: "Component compatibility", constraints: ["compat-*"], repair: "bus" },
];

const RANK: Record<EngStatus, number> = { FAIL: 0, WATCH: 1, PASS: 2, "NOT MODELLED": 3, ANALYSING: 4, STALE: 5 };

const matches = (pattern: string, id: string) => (pattern.endsWith("*") ? id.startsWith(pattern.slice(0, -1)) : pattern === id);

export interface GateResult {
  gate: GateDef;
  status: EngStatus;
  constraints: Constraint[];
  /** The constraint that sets the gate status (worst one). */
  driver: Constraint | null;
  /** Subsystem to open for a repair: the driver's own subsystem when the backend names one. */
  repair: ComponentCategory;
}

export function evaluateGates(constraints: readonly Constraint[]): GateResult[] {
  return GATES.map((gate) => {
    const own = constraints.filter((c) => gate.constraints.some((p) => matches(p, c.id)));
    if (own.length === 0) {
      // compatibility has no constraint when every pairing is fine: that is a pass, not unknown
      return { gate, status: gate.id === "compat" ? "PASS" : "NOT MODELLED", constraints: [], driver: null, repair: gate.repair };
    }
    const sorted = [...own].sort((a, b) => RANK[constraintStatus(a)] - RANK[constraintStatus(b)]);
    const modelled = own.filter((c) => c.status !== "not-modelled");
    const status: EngStatus = modelled.length === 0 ? "NOT MODELLED" : constraintStatus(sorted[0]);
    const driver = sorted[0];
    return { gate, status, constraints: own, driver, repair: constraintCategories(driver)[0] ?? gate.repair };
  });
}

export function gateCounts(results: GateResult[]): Record<"PASS" | "WATCH" | "FAIL" | "NOT MODELLED", number> {
  const out = { PASS: 0, WATCH: 0, FAIL: 0, "NOT MODELLED": 0 };
  for (const r of results) if (r.status in out) out[r.status as keyof typeof out] += 1;
  return out;
}

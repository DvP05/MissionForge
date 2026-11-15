/**
 * Engineering status language (front_design.md 6.5): PASS, WATCH, FAIL, NOT MODELLED,
 * ANALYSING, STALE. Statuses come from backend constraint results; ANALYSING / STALE come
 * from comparing the analysis revision with the current design revision. Nothing here
 * computes an engineering value.
 */
import type { components } from "@/lib/api/schema";
import type { ComponentCategory } from "./part-registry";

type Constraint = components["schemas"]["ConstraintResult"];

export type EngStatus = "PASS" | "WATCH" | "FAIL" | "NOT MODELLED" | "ANALYSING" | "STALE";

export function constraintStatus(c: Constraint | undefined): EngStatus {
  if (!c) return "NOT MODELLED";
  switch (c.status) {
    case "pass":
      return "PASS";
    case "warning":
      return "WATCH";
    case "fail":
      return "FAIL";
    default:
      return "NOT MODELLED";
  }
}

export const STATUS_TONE: Record<EngStatus, string> = {
  PASS: "border-accent-green/50 text-accent-green",
  WATCH: "border-accent-amber/60 text-accent-amber",
  FAIL: "border-accent-red/60 text-accent-red",
  "NOT MODELLED": "border-border text-muted",
  ANALYSING: "border-accent-blue/60 text-accent-blue",
  STALE: "border-accent-violet/60 text-accent-violet",
};

/** Backend `impactedSubsystems` names -> catalogue categories (for linking only). */
const SUBSYSTEM_CATEGORIES: Record<string, ComponentCategory[]> = {
  communications: ["communications", "ground"],
  data: ["cdh", "communications"],
  payload: ["instrument"],
  science: ["instrument"],
  power: ["power"],
  thermal: ["thermal"],
  mass: ["bus", "launch"],
  launch: ["launch"],
  bus: ["bus"],
  trajectory: ["propulsion"],
  propulsion: ["propulsion"],
  adcs: ["adcs"],
  pointing: ["adcs"],
  cdh: ["cdh"],
  ground: ["ground"],
};

/** Constraint ids whose subject is plain from the id even when no subsystem is listed. */
const ID_CATEGORIES: [RegExp, ComponentCategory[]][] = [
  [/^mass-/, ["bus", "launch"]],
  [/^delta-v/, ["propulsion"]],
  [/^(peak-power|energy-|battery-)/, ["power"]],
  [/^data-buffer/, ["cdh"]],
  [/^data-return/, ["communications", "cdh"]],
  [/^link-/, ["communications", "ground"]],
  [/^thermal/, ["thermal"]],
  [/^pointing/, ["adcs"]],
  [/^science-/, ["instrument"]],
  [/^trajectory/, ["propulsion"]],
];

/** Which catalogue categories a constraint concerns (empty when it is mission-wide). */
export function constraintCategories(c: Constraint): ComponentCategory[] {
  const out = new Set<ComponentCategory>();
  for (const s of c.impactedSubsystems ?? []) for (const cat of SUBSYSTEM_CATEGORIES[s] ?? []) out.add(cat);
  for (const [re, cats] of ID_CATEGORIES) if (re.test(c.id)) cats.forEach((cat) => out.add(cat));
  return [...out];
}

export function constraintsFor(constraints: readonly Constraint[], category: ComponentCategory): Constraint[] {
  return constraints.filter((c) => constraintCategories(c).includes(category));
}

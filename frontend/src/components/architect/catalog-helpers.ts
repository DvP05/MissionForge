import type { components } from "@/lib/api/schema";
import type { ComponentCategory, MissionState } from "@/state/mission-store";

type Schemas = components["schemas"];
export type CatalogComponent = Schemas["CatalogComponent"];
export type CatalogGroup = Schemas["CatalogGroup"];
type Rule = Schemas["CompatibilityRule"];

export const CATEGORY_ORDER: { category: ComponentCategory; label: string; multi?: boolean }[] = [
  { category: "launch", label: "Launch" },
  { category: "bus", label: "Bus" },
  { category: "propulsion", label: "Propulsion" },
  { category: "power", label: "Power" },
  { category: "adcs", label: "ADCS" },
  { category: "communications", label: "Communications" },
  { category: "thermal", label: "Thermal" },
  { category: "cdh", label: "C&DH" },
  { category: "instrument", label: "Instruments", multi: true },
  { category: "ground", label: "Ground" },
];

const FIELD = {
  launch: "launchVehicleId",
  bus: "busId",
  propulsion: "propulsionId",
  power: "powerId",
  adcs: "adcsId",
  communications: "communicationsId",
  thermal: "thermalId",
  cdh: "cdhId",
  ground: "groundSegmentId",
} as const;

/** Parameters worth showing first, per category (others appear under "all parameters"). */
export const KEY_PARAMETERS: Record<ComponentCategory, string[]> = {
  launch: ["launch_mass_limit", "cost"],
  bus: ["max_payload_mass", "mass", "power_w", "cost"],
  propulsion: ["isp", "propellant_capacity", "dry_mass", "cost"],
  power: ["array_power_at_1au", "battery_capacity", "mass", "cost"],
  adcs: ["pointing_accuracy", "mass", "power_w", "cost"],
  communications: ["max_data_rate", "tx_power", "antenna_gain", "mass", "cost"],
  thermal: ["mass", "power_w", "cost"],
  cdh: ["storage", "mass", "power_w", "cost"],
  instrument: ["data_rate", "mass", "power_w", "cost"],
  ground: ["station_gain", "contact_availability", "noise_temperature", "cost"],
};

/** Currently selected component ids for a category (one id, or the instrument list). */
export function selectedIds(mission: MissionState, category: ComponentCategory): string[] {
  if (category === "instrument") return [...mission.architecture.instrumentIds];
  return [mission.architecture[FIELD[category]]];
}

export function allSelectedIds(mission: MissionState): string[] {
  return CATEGORY_ORDER.flatMap(({ category }) => selectedIds(mission, category));
}

export function indexCatalog(groups: CatalogGroup[]): Map<string, CatalogComponent> {
  const map = new Map<string, CatalogComponent>();
  for (const g of groups) for (const c of g.components) map.set(c.id, c);
  return map;
}

export interface CompatConflict {
  /** The component whose compatibility rule is not met. */
  componentId: string;
  /** The other component named in the rule. */
  otherId: string;
  message: string;
  /** The selection that is not the candidate: the one that would be affected. */
  affectedId: string;
}

function ruleMatches(rule: Rule, other: CatalogComponent): boolean {
  if (rule.ids && !rule.ids.includes(other.id)) return false;
  if (rule.tags && !rule.tags.some((t) => (other.tags ?? []).includes(t))) return false;
  return true;
}

function violations(owner: CatalogComponent, others: CatalogComponent[]): CompatConflict[] {
  const rules = owner.compatibleWith ?? [];
  const out: CompatConflict[] = [];
  for (const category of new Set(rules.map((r) => r.category))) {
    const inCategory = rules.filter((r) => r.category === category);
    for (const other of others) {
      if (other.category !== category || other.id === owner.id) continue;
      if (!inCategory.some((r) => ruleMatches(r, other))) {
        out.push({
          componentId: owner.id,
          otherId: other.id,
          message: `${owner.name} is not compatible with ${other.name} (${category}).`,
          affectedId: other.id,
        });
      }
    }
  }
  return out;
}

/**
 * Pre-commit warning only: rules involving `candidate` against the other current
 * selections, in both directions. The authoritative result is the backend compat-*
 * constraint after the revision is analysed.
 */
export function conflictsForCandidate(
  catalog: Map<string, CatalogComponent>,
  mission: MissionState,
  category: ComponentCategory,
  candidateId: string,
): CompatConflict[] {
  const candidate = catalog.get(candidateId);
  if (!candidate) return [];
  // Other categories, plus (for instruments) the other selected instruments, since the backend
  // also checks same-category rules. A single selection being replaced is excluded.
  const otherIds = CATEGORY_ORDER.filter((c) => c.category !== category).flatMap(({ category: cat }) =>
    selectedIds(mission, cat),
  );
  if (category === "instrument") {
    otherIds.push(...selectedIds(mission, category).filter((id) => id !== candidateId));
  }
  const others = otherIds.map((id) => catalog.get(id))
    .filter((c): c is CatalogComponent => c !== undefined);
  const conflicts = violations(candidate, others);
  for (const other of others) {
    conflicts.push(...violations(other, [candidate]).map((v) => ({ ...v, affectedId: other.id })));
  }
  return conflicts;
}

/** Catalogue `cost` parameter (USD) or null when the component has none. */
export function catalogCost(c: CatalogComponent | undefined): number | null {
  const q = c?.parameters.cost;
  return q && Number.isFinite(q.value) ? q.value : null;
}

/** Catalogue list-cost difference for choosing `candidate` (display only). */
export function costDelta(
  catalog: Map<string, CatalogComponent>,
  mission: MissionState,
  category: ComponentCategory,
  candidate: CatalogComponent,
): number | null {
  const next = catalogCost(candidate);
  if (next === null) return null;
  if (category === "instrument") {
    return selectedIds(mission, category).includes(candidate.id) ? -next : next;
  }
  const current = catalogCost(catalog.get(selectedIds(mission, category)[0]));
  return current === null ? null : next - current;
}

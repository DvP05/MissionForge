/**
 * Component-to-geometry mapping layer (front_design.md 5.4).
 *
 * Maps catalogue components in the canonical MissionState onto 3D presentation: a mount point,
 * a procedural placeholder shape, position / orientation, an exploded-view offset and a
 * subsystem group for view modes. It is presentation only: no engineering number is computed
 * here, and nothing in it is read back into the mission design.
 *
 * The catalogue supplies no dimensions, so EVERY shape is an illustrative placeholder
 * (`geometryStatus: "placeholder"`). Where a variant differs in size (a bigger dish, more
 * solar panels) the size follows the component's rank within its own category, never a
 * physical dimension; the viewport says so in its technical mode.
 */
import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type CatalogComponent = Schemas["CatalogComponent"];
export type ComponentCategory = CatalogComponent["category"];
type Architecture = Schemas["MissionState"]["architecture"];

export type Vec3 = [number, number, number];

/** Visual subsystem groups used by the view modes (highlight / isolate). */
export type SubsystemGroup = "structure" | "power" | "propulsion" | "communications" | "avionics" | "thermal" | "science";

export type PartKind =
  | "bus"
  | "solar-array"
  | "antenna-patch"
  | "antenna-dish"
  | "nozzle-cluster"
  | "chemical-engine"
  | "ion-engine"
  | "reaction-wheels"
  | "star-tracker"
  | "insulation"
  | "heater-strips"
  | "radiator"
  | "avionics-box"
  | "camera"
  | "spectrometer"
  | "radiometer"
  | "boom"
  | "launch-adapter";

export interface PartVisual {
  componentId: string;
  name: string;
  category: ComponentCategory;
  group: SubsystemGroup;
  kind: PartKind;
  /** Stable mount-point id; a replacement in the same slot keeps it. */
  mountId: string;
  mountLabel: string;
  position: Vec3;
  rotation: Vec3;
  /** Unit direction the part travels along when exploded or installed. */
  normal: Vec3;
  explodeDistance: number;
  /** 0..1 visual size from the component's rank in its category (not a dimension). */
  sizeRank: number;
  /** Extra variant data for the shape builder (e.g. dish radius, panel count). */
  variant: Record<string, number>;
  colour: string;
  geometryStatus: "placeholder";
}

export interface MountPoint {
  mountId: string;
  label: string;
  category: ComponentCategory;
  position: Vec3;
  normal: Vec3;
}

export const GROUP_OF: Record<ComponentCategory, SubsystemGroup> = {
  launch: "structure",
  bus: "structure",
  propulsion: "propulsion",
  power: "power",
  adcs: "avionics",
  communications: "communications",
  thermal: "thermal",
  cdh: "avionics",
  instrument: "science",
  ground: "communications",
};

export const GROUP_COLOUR: Record<SubsystemGroup, string> = {
  structure: "#9aaac1",
  power: "#ffb547",
  propulsion: "#ff7a59",
  communications: "#35d8f2",
  avionics: "#4d8dff",
  thermal: "#ff5c68",
  science: "#9b7cff",
};

/** Ground stations are not part of the spacecraft and are never drawn in 3D. */
export const OFF_SPACECRAFT: ReadonlySet<ComponentCategory> = new Set<ComponentCategory>(["ground"]);

const MAX_INSTRUMENT_SLOTS = 6;

const has = (c: CatalogComponent, tag: string) =>
  (c.tags ?? []).includes(tag) || (c.capabilities ?? []).includes(tag);

const param = (c: CatalogComponent | undefined, key: string): number | null => {
  const q = c?.parameters[key];
  return q && Number.isFinite(q.value) ? q.value : null;
};

/**
 * Rank (0..1) of `component` among its catalogue category by `key`; 0.5 when unknown.
 * Visual sizing only.
 */
export function sizeRank(index: Map<string, CatalogComponent>, component: CatalogComponent, key: string): number {
  const values = [...index.values()]
    .filter((c) => c.category === component.category)
    .map((c) => param(c, key))
    .filter((v): v is number => v !== null)
    .sort((a, b) => a - b);
  const v = param(component, key);
  if (v === null || values.length < 2) return 0.5;
  const lo = values[0];
  const hi = values[values.length - 1];
  return hi === lo ? 0.5 : (v - lo) / (hi - lo);
}

/** Half-size of the bus box for a bus component (by its catalogue size rank). */
export function busHalfSize(index: Map<string, CatalogComponent>, bus: CatalogComponent | undefined): number {
  if (!bus) return 0.6;
  return 0.42 + 0.38 * sizeRank(index, bus, "max_payload_mass");
}

/** Instrument slots on the +z (nadir / target-facing) panel. */
/**
 * Payload slots on the +Z panel. The grid adapts to the panel size so instruments (about
 * 0.3 m across) never share space: a small bus gets 2 columns x 3 rows, a larger one 3 x 2.
 */
export function instrumentSlot(i: number, h: number): Vec3 {
  const cols = h < 0.55 ? 2 : 3;
  const rows = Math.ceil(MAX_INSTRUMENT_SLOTS / cols);
  const pitchX = (2 * h) / cols;
  const pitchY = (2 * h) / rows;
  const c = i % cols;
  const r = Math.floor(i / cols) % rows;
  return [-h + pitchX * (c + 0.5), h - pitchY * (r + 0.5), h];
}

/** Every mount point of a spacecraft with bus half-size `h` (used for technical overlays). */
export function mountPoints(h: number): MountPoint[] {
  const base: MountPoint[] = [
    { mountId: "mount-bus", label: "Primary structure", category: "bus", position: [0, 0, 0], normal: [0, 0, 0] },
    { mountId: "mount-power", label: "Solar array hinges (±X)", category: "power", position: [0, 0, 0], normal: [0, 0, -1] },
    { mountId: "mount-comms", label: "Antenna mast (+Y deck)", category: "communications", position: [0, h, 0], normal: [0, 1, 0] },
    { mountId: "mount-propulsion", label: "Thrust axis (−Y)", category: "propulsion", position: [0, -h, 0], normal: [0, -1, 0] },
    // One job per face: -X carries attitude (upper, aft) and avionics (lower, forward), clear of
    // the wing plane (z = 0); -Z is the radiator; +Z the payload; -Y thrust; +Y the antenna.
    { mountId: "mount-adcs", label: "ADCS bay (−X face, upper aft)", category: "adcs", position: [-h, 0.5 * h, -0.5 * h], normal: [-1, 0, 0] },
    { mountId: "mount-thermal", label: "Radiator face (−Z)", category: "thermal", position: [0, 0, -h], normal: [0, 0, -1] },
    { mountId: "mount-cdh", label: "Avionics shelf (−X face, lower forward)", category: "cdh", position: [-h, -0.5 * h, 0.5 * h + 0.04], normal: [-1, 0, 0] },
    { mountId: "mount-launch", label: "Launch adapter ring", category: "launch", position: [0, -h - 0.66, 0], normal: [0, -1, 0] },
    { mountId: "mount-boom", label: "Magnetometer boom root (+Z lower edge)", category: "instrument", position: [0.6 * h, -h, h], normal: [0.52, -0.38, 0.76] },
  ];
  for (let i = 0; i < MAX_INSTRUMENT_SLOTS; i += 1) {
    base.push({
      mountId: `mount-instrument-${i + 1}`,
      label: `Payload slot ${i + 1} (+Z panel)`,
      category: "instrument",
      position: instrumentSlot(i, h),
      normal: [0, 0, 1],
    });
  }
  return base;
}

function visualFor(
  c: CatalogComponent,
  index: Map<string, CatalogComponent>,
  h: number,
  mount: MountPoint,
): Omit<PartVisual, "componentId" | "name" | "category" | "group" | "mountId" | "mountLabel" | "geometryStatus"> {
  const colour = GROUP_COLOUR[GROUP_OF[c.category]];
  const common = { position: mount.position, normal: mount.normal, rotation: [0, 0, 0] as Vec3, colour };
  // Euler XYZ applies Z first: local +Y is swung to +X, then tipped forward and down, so the boom
  // points out to the side, away from the nozzle and the payload (about (0.52, -0.38, 0.76)).
  if (mount.mountId === "mount-boom") common.rotation = [2.03, 0, -0.55];
  switch (c.category) {
    case "bus":
      return { ...common, kind: "bus", explodeDistance: 0, sizeRank: sizeRank(index, c, "max_payload_mass"), variant: { h } };
    case "power": {
      const r = sizeRank(index, c, "array_power_at_1au");
      return { ...common, kind: "solar-array", explodeDistance: 1.1, sizeRank: r, variant: { h, panels: 1 + Math.round(r * 3) } };
    }
    case "communications": {
      if (has(c, "low-gain")) {
        return { ...common, kind: "antenna-patch", explodeDistance: 0.9, sizeRank: 0, variant: { h } };
      }
      const r = sizeRank(index, c, "antenna_gain");
      return { ...common, kind: "antenna-dish", explodeDistance: 1.0, sizeRank: r, variant: { h, radius: 0.28 + 0.42 * r, ka: has(c, "ka-band") ? 1 : 0 } };
    }
    case "propulsion": {
      if (has(c, "electric")) return { ...common, kind: "ion-engine", explodeDistance: 1.0, sizeRank: 0.5, variant: { h } };
      if (has(c, "cold-gas")) return { ...common, kind: "nozzle-cluster", explodeDistance: 0.9, sizeRank: 0.2, variant: { h } };
      return { ...common, kind: "chemical-engine", explodeDistance: 1.0, sizeRank: has(c, "biprop") ? 1 : 0.5, variant: { h, tanks: has(c, "biprop") ? 2 : 1 } };
    }
    case "adcs":
      // geometry is modelled pointing +Y; rotate it to face out of the -X side
      common.rotation = [0, 0, Math.PI / 2];
      return has(c, "star-tracker")
        ? { ...common, kind: "star-tracker", explodeDistance: 0.8, sizeRank: has(c, "precision") ? 1 : 0.5, variant: { h, heads: has(c, "precision") ? 2 : 1 } }
        : { ...common, kind: "reaction-wheels", explodeDistance: 0.8, sizeRank: 0.3, variant: { h } };
    case "thermal":
      if (has(c, "radiator")) return { ...common, kind: "radiator", explodeDistance: 0.9, sizeRank: 1, variant: { h } };
      if (has(c, "heaters")) return { ...common, kind: "heater-strips", explodeDistance: 0.7, sizeRank: 0.5, variant: { h } };
      return { ...common, position: [0, 0, 0], kind: "insulation", explodeDistance: 0, sizeRank: 0.3, variant: { h } };
    case "cdh":
      return { ...common, kind: "avionics-box", explodeDistance: 0.8, sizeRank: sizeRank(index, c, "storage"), variant: { h } };
    case "instrument": {
      const kind: PartKind = has(c, "fields")
        ? "boom"
        : has(c, "spectrometer")
          ? "spectrometer"
          : has(c, "radiometer")
            ? "radiometer"
            : "camera";
      return { ...common, kind, explodeDistance: 0.9, sizeRank: sizeRank(index, c, "mass"), variant: { h, large: has(c, "high-data-rate") ? 1 : 0 } };
    }
    case "launch":
      return { ...common, kind: "launch-adapter", explodeDistance: 0.9, sizeRank: 0.5, variant: { h } };
    case "ground":
      throw new Error("ground segment has no spacecraft geometry");
  }
}

const SINGLE: { category: Exclude<ComponentCategory, "instrument" | "ground">; field: keyof Architecture }[] = [
  { category: "bus", field: "busId" },
  { category: "power", field: "powerId" },
  { category: "communications", field: "communicationsId" },
  { category: "propulsion", field: "propulsionId" },
  { category: "adcs", field: "adcsId" },
  { category: "thermal", field: "thermalId" },
  { category: "cdh", field: "cdhId" },
  { category: "launch", field: "launchVehicleId" },
];

/**
 * The parts to draw for an architecture. Unknown component ids (not in the catalogue) are
 * skipped: the viewport never invents a part the catalogue does not have.
 */
export function partsForArchitecture(architecture: Architecture, index: Map<string, CatalogComponent>): PartVisual[] {
  const bus = index.get(architecture.busId);
  const h = busHalfSize(index, bus);
  const mounts = mountPoints(h);
  const mountFor = (category: ComponentCategory, slot = 0) =>
    category === "instrument"
      ? mounts.find((m) => m.mountId === (slot < 0 ? "mount-boom" : `mount-instrument-${slot + 1}`))!
      : mounts.find((m) => m.category === category && m.mountId !== "mount-boom")!;

  const out: PartVisual[] = [];
  const push = (id: string, category: ComponentCategory, slot = 0) => {
    const c = index.get(id);
    if (!c || OFF_SPACECRAFT.has(category)) return;
    const mount = mountFor(category, slot);
    out.push({
      componentId: c.id,
      name: c.name.replace(/^Archetype:\s*/, ""),
      category,
      group: GROUP_OF[category],
      mountId: mount.mountId,
      mountLabel: mount.label,
      geometryStatus: "placeholder",
      ...visualFor(c, index, h, mount),
    });
  };
  for (const { category, field } of SINGLE) push(architecture[field] as string, category);
  // a fields instrument rides its own boom; every other instrument takes the next payload slot
  let slot = 0;
  for (const id of architecture.instrumentIds) {
    const c = index.get(id);
    if (!c) continue;
    if (has(c, "fields")) push(id, "instrument", -1);
    else if (slot < MAX_INSTRUMENT_SLOTS) push(id, "instrument", slot++);
  }
  return out;
}

/** Where a component sits (or would sit), for the inspector; null for off-spacecraft parts. */
export function installationLabel(category: ComponentCategory, slot = 0): string {
  if (category === "ground") return "Ground segment (not on the spacecraft)";
  const m = mountPoints(0.6).find((p) =>
    category === "instrument" ? p.mountId === `mount-instrument-${slot + 1}` : p.category === category,
  );
  return m?.label ?? "Unassigned";
}

/** View modes (front_design.md 5.6). Highlight modes are visual only, never a simulation. */
export type ViewMode = "assembly" | "exploded" | "subsystem" | "technical" | "power" | "communications" | "science" | "thermal";

export const VIEW_MODES: { mode: ViewMode; label: string; note: string; groups?: SubsystemGroup[] }[] = [
  { mode: "assembly", label: "Assembly", note: "Complete spacecraft." },
  { mode: "exploded", label: "Exploded", note: "Parts moved apart along their mounting axes." },
  { mode: "subsystem", label: "Subsystem", note: "Only the selected part's subsystem is shown." },
  { mode: "technical", label: "Technical", note: "Mount points, labels and wireframe. Shapes are placeholders, not to scale." },
  { mode: "power", label: "Power", note: "Visual highlight of power hardware only; no power-flow simulation.", groups: ["power"] },
  { mode: "communications", label: "Comms", note: "Visual highlight of communications hardware only; link results are in the dashboard.", groups: ["communications"] },
  { mode: "science", label: "Science", note: "Visual highlight of the science payload only.", groups: ["science"] },
  { mode: "thermal", label: "Thermal", note: "Visual highlight of thermal hardware only; no thermal map is simulated.", groups: ["thermal"] },
];

/** How a part is shown in a mode: normal, dimmed, or hidden. */
export function partEmphasis(
  part: PartVisual,
  mode: ViewMode,
  selectedGroup: SubsystemGroup | null,
  highlightIds: ReadonlySet<string>,
): "normal" | "dim" | "hidden" {
  if (highlightIds.size > 0) return highlightIds.has(part.componentId) || part.category === "bus" ? "normal" : "dim";
  if (mode === "subsystem") {
    if (!selectedGroup) return "normal";
    return part.group === selectedGroup || part.category === "bus" ? "normal" : "hidden";
  }
  const groups = VIEW_MODES.find((m) => m.mode === mode)?.groups;
  if (!groups) return "normal";
  return groups.includes(part.group) || part.category === "bus" ? "normal" : "dim";
}

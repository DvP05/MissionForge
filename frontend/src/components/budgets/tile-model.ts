import { formatFraction, formatNumber, formatQuantity, MISSING } from "@/lib/format";
import type { components } from "@/lib/api/schema";
import type { MissionAnalysis } from "@/state/mission-store";

type Provenance = components["schemas"]["Provenance"];
type Quantity = components["schemas"]["Quantity"];

export type TileId = "mass" | "power" | "deltav" | "data" | "cost" | "science";

export interface TileRow {
  key: string;
  label: string;
  /** Display text, or null when the backend gave no number. */
  text: string | null;
  provenance: Provenance;
  /** Raw backend number used only to detect a change between two analyses. */
  raw: number | null;
  /** Why there is no number, when the row itself knows (overrides the panel reason). */
  reason?: string;
}

export interface TileModel {
  id: TileId;
  title: string;
  rows: TileRow[];
}

/** Constraint ids the backend uses when the engine could not run (numbers are placeholders). */
const FAILURE_IDS = ["catalog-item-not-found", "model-input-invalid"];

export function analysisFailed(a: MissionAnalysis): boolean {
  return a.constraints.some((c) => FAILURE_IDS.includes(c.id));
}

const PLACEHOLDER_REASON = "Analysis could not run; placeholder value, not a result";

/**
 * Provenance for engine-computed scalars that the API ships without a record of their own.
 * Deliberately generic: no specific scenario assumption is attributed to these numbers.
 */
export function analysisProvenance(a: MissionAnalysis): Provenance {
  return {
    fidelity: "derived",
    sourceName: "MISSIONFORGE analysis engine",
    sourceVersion: a.engineVersion,
    assumptions: [
      "Computed by the engine from catalogue values that are gameplay-estimates; see the full assumption list in the drawer.",
    ],
  };
}

export function quantityRow(key: string, label: string, quantity: Quantity | undefined): TileRow {
  // A not-modelled Quantity is a placeholder (e.g. failed analysis): never shown as a number.
  if (quantity && quantity.provenance.fidelity === "not-modelled") {
    return {
      key,
      label,
      text: null,
      provenance: quantity.provenance,
      raw: null,
      reason: quantity.provenance.assumptions?.[0] ?? PLACEHOLDER_REASON,
    };
  }
  return {
    key,
    label,
    text: quantity ? (formatQuantity(quantity) === MISSING ? null : formatQuantity(quantity)) : null,
    provenance: quantity?.provenance ?? { fidelity: "not-modelled", sourceName: "No value reported" },
    raw: quantity && Number.isFinite(quantity.value) ? quantity.value : null,
  };
}

export function scalarRow(
  a: MissionAnalysis,
  key: string,
  label: string,
  value: number | undefined,
  render: (v: number) => string,
): TileRow {
  if (analysisFailed(a)) {
    return { key, label, text: null, provenance: analysisProvenance(a), raw: null, reason: PLACEHOLDER_REASON };
  }
  const ok = value !== undefined && Number.isFinite(value);
  return {
    key,
    label,
    text: ok ? render(value) : null,
    provenance: analysisProvenance(a),
    raw: ok ? value : null,
  };
}

/** Maps backend budget fields onto tiles. Values are passed through, never recomputed. */
export function buildTiles(a: MissionAnalysis): TileModel[] {
  const b = a.budgets;
  return [
    {
      id: "mass",
      title: "Mass",
      rows: [
        quantityRow("wet", "Wet mass", b.wetMassKg),
        quantityRow("dry", "Dry mass", b.dryMassKg),
        quantityRow("prop", "Propellant", b.propellantMassKg),
        scalarRow(a, "margin", "Mass margin", b.massMarginFraction, formatFraction),
      ],
    },
    {
      id: "power",
      title: "Power and energy",
      rows: [
        quantityRow("avg", "Average power", b.averagePowerW),
        quantityRow("peak", "Peak power", b.peakPowerW),
        scalarRow(a, "margin", "Energy margin", b.energyMarginFraction, formatFraction),
      ],
    },
    {
      id: "deltav",
      title: "Delta-v",
      rows: [
        quantityRow("avail", "Available", b.availableDeltaVKmPerS),
        quantityRow("req", "Required", b.requiredDeltaVKmPerS),
        scalarRow(a, "margin", "Margin after reserve", b.deltaVMarginKmPerS, (v) => `${formatNumber(v)} km/s`),
      ],
    },
    {
      id: "data",
      title: "Data",
      rows: [
        quantityRow("gen", "Generated", b.dataGeneratedBits),
        quantityRow("down", "Downlinked", b.dataDownlinkedBits),
        scalarRow(a, "margin", "Downlink margin", b.dataMarginFraction, formatFraction),
      ],
    },
    { id: "cost", title: "Cost", rows: [q("cost", "Estimated cost", b.estimatedCostUsd)] },
    {
      id: "science",
      title: "Science",
      rows: [
        scalarRow(a, "coverage", "Coverage score", a.science.coverageScore, (v) => `${formatNumber(v)} %`),
        scalarRow(a, "returned", "Data returned", a.science.returnedFraction, formatFraction),
        scalarRow(a, "collected", "Data collected", a.science.collectedFraction, formatFraction),
      ],
    },
  ];
}

/** True when any value in the tile differs between two analyses (highlighting only). */
export function tileChanged(prev: TileModel | undefined, next: TileModel): boolean {
  if (!prev) return false;
  return next.rows.some((row, i) => prev.rows[i]?.raw !== row.raw);
}

const NO_VALUE: Provenance = { fidelity: "not-modelled", sourceName: "No analysis yet" };

function empty(key: string, label: string): TileRow {
  return { key, label, text: null, provenance: NO_VALUE, raw: null };
}

/** Same tiles with no numbers, for before the first analysis arrives. */
export function placeholderTiles(): TileModel[] {
  return [
    { id: "mass", title: "Mass", rows: [empty("wet", "Wet mass"), empty("dry", "Dry mass"), empty("prop", "Propellant"), empty("margin", "Mass margin")] },
    { id: "power", title: "Power and energy", rows: [empty("avg", "Average power"), empty("peak", "Peak power"), empty("margin", "Energy margin")] },
    { id: "deltav", title: "Delta-v", rows: [empty("avail", "Available"), empty("req", "Required"), empty("margin", "Margin after reserve")] },
    { id: "data", title: "Data", rows: [empty("gen", "Generated"), empty("down", "Downlinked"), empty("margin", "Downlink margin")] },
    { id: "cost", title: "Cost", rows: [empty("cost", "Estimated cost")] },
    { id: "science", title: "Science", rows: [empty("coverage", "Coverage score"), empty("returned", "Data returned"), empty("collected", "Data collected")] },
  ];
}

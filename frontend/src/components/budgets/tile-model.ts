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
}

export interface TileModel {
  id: TileId;
  title: string;
  rows: TileRow[];
}

/** Provenance for backend-derived scalars that the API ships without their own record. */
export function analysisProvenance(a: MissionAnalysis): Provenance {
  return {
    fidelity: "derived",
    sourceName: "MISSIONFORGE analysis engine",
    sourceVersion: a.engineVersion,
    assumptions: a.assumptions.slice(0, 4),
  };
}

function q(key: string, label: string, quantity: Quantity | undefined): TileRow {
  return {
    key,
    label,
    text: quantity ? (formatQuantity(quantity) === MISSING ? null : formatQuantity(quantity)) : null,
    provenance: quantity?.provenance ?? { fidelity: "not-modelled", sourceName: "No value reported" },
    raw: quantity && Number.isFinite(quantity.value) ? quantity.value : null,
  };
}

function scalar(
  a: MissionAnalysis,
  key: string,
  label: string,
  value: number | undefined,
  render: (v: number) => string,
): TileRow {
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
        q("wet", "Wet mass", b.wetMassKg),
        q("dry", "Dry mass", b.dryMassKg),
        q("prop", "Propellant", b.propellantMassKg),
        scalar(a, "margin", "Mass margin", b.massMarginFraction, formatFraction),
      ],
    },
    {
      id: "power",
      title: "Power and energy",
      rows: [
        q("avg", "Average power", b.averagePowerW),
        q("peak", "Peak power", b.peakPowerW),
        scalar(a, "margin", "Energy margin", b.energyMarginFraction, formatFraction),
      ],
    },
    {
      id: "deltav",
      title: "Delta-v",
      rows: [
        q("avail", "Available", b.availableDeltaVKmPerS),
        q("req", "Required", b.requiredDeltaVKmPerS),
        scalar(a, "margin", "Margin after reserve", b.deltaVMarginKmPerS, (v) => `${formatNumber(v)} km/s`),
      ],
    },
    {
      id: "data",
      title: "Data",
      rows: [
        q("gen", "Generated", b.dataGeneratedBits),
        q("down", "Downlinked", b.dataDownlinkedBits),
        scalar(a, "margin", "Downlink margin", b.dataMarginFraction, formatFraction),
      ],
    },
    { id: "cost", title: "Cost", rows: [q("cost", "Estimated cost", b.estimatedCostUsd)] },
    {
      id: "science",
      title: "Science",
      rows: [
        scalar(a, "coverage", "Coverage score", a.science.coverageScore, (v) => `${formatNumber(v)} %`),
        scalar(a, "returned", "Data returned", a.science.returnedFraction, formatFraction),
        scalar(a, "collected", "Data collected", a.science.collectedFraction, formatFraction),
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

import { formatNumber, MISSING } from "@/lib/format";
import type { MissionAnalysis } from "@/state/mission-store";
import { quantityRow, scalarRow, type TileRow } from "@/components/budgets/tile-model";

/**
 * Trade-study table rows. `key` is the exact key the backend uses in `deltas`
 * (backend/app/domain/analysis/trade.py TRADE_METRICS). Labels and units here are display
 * metadata only; every number comes from the API (analysis fields or `deltas`).
 */
export interface CompareMetric {
  key: string;
  label: string;
  unit: string;
  read: (a: MissionAnalysis) => TileRow;
}

export const COMPARE_METRICS: CompareMetric[] = [
  { key: "dry_mass_kg", label: "Dry mass", unit: "kg", read: (a) => quantityRow("dry", "Dry mass", a.budgets.dryMassKg) },
  { key: "wet_mass_kg", label: "Wet mass", unit: "kg", read: (a) => quantityRow("wet", "Wet mass", a.budgets.wetMassKg) },
  { key: "average_power_w", label: "Average power", unit: "W", read: (a) => quantityRow("avg", "Average power", a.budgets.averagePowerW) },
  { key: "peak_power_w", label: "Peak power", unit: "W", read: (a) => quantityRow("peak", "Peak power", a.budgets.peakPowerW) },
  { key: "data_generated_bit", label: "Data generated", unit: "bit", read: (a) => quantityRow("gen", "Data generated", a.budgets.dataGeneratedBits) },
  { key: "data_downlinked_bit", label: "Data downlinked", unit: "bit", read: (a) => quantityRow("down", "Data downlinked", a.budgets.dataDownlinkedBits) },
  {
    key: "delta_v_margin_km_per_s",
    label: "Delta-v margin",
    unit: "km/s",
    read: (a) => scalarRow(a, "dvm", "Delta-v margin", a.budgets.deltaVMarginKmPerS, (v) => `${formatNumber(v)} km/s`),
  },
  { key: "estimated_cost_usd", label: "Estimated cost", unit: "USD", read: (a) => quantityRow("cost", "Estimated cost", a.budgets.estimatedCostUsd) },
  {
    key: "science_coverage_score",
    label: "Science coverage score",
    unit: "%",
    read: (a) => scalarRow(a, "cov", "Science coverage score", a.science.coverageScore, (v) => `${formatNumber(v)} %`),
  },
  {
    key: "total_score",
    label: "Total score",
    unit: "points",
    read: (a) => scalarRow(a, "score", "Total score", a.score.total, (v) => `${formatNumber(v)} points`),
  },
];

export type Direction = "up" | "down" | "none" | "undefined";

/** Differences smaller than this are float noise from the backend, shown as "no change". */
const NOISE = 1e-9;

export interface DeltaView {
  direction: Direction;
  /** Visible words (never colour alone): "higher by +2 kg", "lower by -1 kg", "no change". */
  text: string;
}

/** Describes one backend delta (alternative minus baseline). `undefined` means the API omitted it. */
export function describeDelta(delta: number | undefined, unit: string): DeltaView {
  if (delta === undefined || !Number.isFinite(delta)) {
    return { direction: "undefined", text: `${MISSING} no difference reported` };
  }
  if (Math.abs(delta) < NOISE) return { direction: "none", text: "no change" };
  const magnitude = `${delta > 0 ? "+" : "-"}${formatNumber(Math.abs(delta))} ${unit}`;
  return delta > 0
    ? { direction: "up", text: `higher by ${magnitude}` }
    : { direction: "down", text: `lower by ${magnitude}` };
}

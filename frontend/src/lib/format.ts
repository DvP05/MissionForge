import type { components } from "@/lib/api/schema";

type Quantity = components["schemas"]["Quantity"];

/** The dash used wherever a number is missing; always paired with a reason, never 0. */
export const MISSING = "—";

const COMPACT = new Intl.NumberFormat("en-US", { notation: "compact", maximumSignificantDigits: 4 });
const PLAIN = new Intl.NumberFormat("en-US", { maximumSignificantDigits: 5 });

/** Display-only number formatting (no unit conversion, no rounding of stored values). */
export function formatNumber(value: number): string {
  if (!Number.isFinite(value)) return MISSING;
  return Math.abs(value) >= 100_000 ? COMPACT.format(value) : PLAIN.format(value);
}

/** "123.4 kg", "$4M"-style values keep the backend unit string; null/non-finite -> dash. */
export function formatQuantity(q: Quantity | null | undefined): string {
  if (!q || !Number.isFinite(q.value)) return MISSING;
  const unit = q.unit === "USD" || q.unit === "USD_2026" ? "USD" : q.unit;
  return `${formatNumber(q.value)} ${unit}`;
}

/** Signed display of a catalogue cost difference. */
export function formatSigned(value: number, unit: string): string {
  if (!Number.isFinite(value)) return MISSING;
  if (value === 0) return `no change (0 ${unit})`;
  return `${value > 0 ? "+" : "-"}${formatNumber(Math.abs(value))} ${unit}`;
}

/** Backend fraction (0..1) shown as a percentage. Display only. */
export function formatFraction(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return MISSING;
  return `${PLAIN.format(value * 100)} %`;
}

/** "cost" -> "Cost", "power_w" -> "Power w" */
export function humanize(key: string): string {
  const text = key.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

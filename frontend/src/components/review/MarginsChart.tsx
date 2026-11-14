"use client";

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

import { FidelityBadge } from "@/components/common/FidelityBadge";
import { ProvenancePopover } from "@/components/common/ProvenancePopover";
import { analysisFailed, analysisProvenance } from "@/components/budgets/tile-model";
import { formatFraction } from "@/lib/format";
import type { RunData } from "@/lib/persistence/run-cache";

/** Constraint ids whose backend marginFraction is plotted (margins are never recomputed here). */
const MARGINS = [
  { id: "mass-margin", label: "Mass" },
  { id: "energy-closure", label: "Energy" },
  { id: "delta-v-margin", label: "Delta-v" },
  { id: "data-buffer", label: "Data" },
  { id: "budget", label: "Budget" },
] as const;

export function MarginsChart({ analysis }: { analysis: RunData["analysis"] }) {
  const failed = analysisFailed(analysis);
  const rows: { label: string; margin: number | null }[] = MARGINS.map((m) => {
    const c = analysis.constraints.find((x) => x.id === m.id);
    const v = c?.marginFraction;
    return { label: m.label, margin: typeof v === "number" && Number.isFinite(v) && c?.status !== "not-modelled" ? v * 100 : null };
  });
  const plotted = rows.filter((r): r is { label: string; margin: number } => r.margin !== null);
  const provenance = analysisProvenance(analysis);
  return (
    <section data-testid="review-margins" aria-labelledby="margins-h" className="space-y-2">
      <h2 id="margins-h" className="text-lg font-semibold">Design margins</h2>
      <p className="text-sm text-muted">
        Design-time margins from the engineering analysis of this run&apos;s input design. They are not re-measured
        during the flown run.
      </p>
      {failed || plotted.length === 0 ? (
        <p className="text-sm text-muted">— No margins available: the analysis could not run or reported none.</p>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <FidelityBadge fidelity={provenance.fidelity} />
            <ProvenancePopover provenance={provenance} label="design margins" />
          </div>
          <div role="img" aria-label="Design margins in percent for mass, energy, delta-v, data and budget" className="overflow-hidden">
            <BarChart width={320} height={200} responsive style={{ width: "100%", maxWidth: "100%", height: 200 }} data={plotted} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
              <CartesianGrid stroke="#243044" strokeDasharray="3 3" />
              <XAxis dataKey="label" tick={{ fill: "#8fa0b8", fontSize: 11 }} />
              <YAxis width={48} unit=" %" tick={{ fill: "#8fa0b8", fontSize: 11 }} />
              <Bar dataKey="margin" fill="#22d3ee" isAnimationActive={false} />
            </BarChart>
          </div>
          <ul className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-5">
            {rows.map((r) => (
              <li key={r.label}>
                <span className="text-muted">{r.label}: </span>
                <span className="tabular-nums">{r.margin === null ? "— not reported" : formatFraction(r.margin / 100)}</span>
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted">Margin as a percent of the limit, reported by the backend per constraint.</p>
        </>
      )}
    </section>
  );
}

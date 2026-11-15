"use client";

import { ChevronUp, Gauge } from "lucide-react";
import { useEffect, useRef } from "react";

import { emphasiseChange } from "@/lib/motion/motion";

import { analysisFailed, quantityRow, scalarRow, type TileRow } from "@/components/budgets/tile-model";
import { constraintStatus, type EngStatus } from "@/lib/spacecraft/engineering-status";
import { formatFraction, formatNumber, formatQuantity, MISSING } from "@/lib/format";
import { useArchitectUi } from "@/state/architect-ui-store";
import { useMissionStore, type MissionAnalysis } from "@/state/mission-store";
import { EngStatusChip } from "./EngStatusChip";

export interface Cell {
  key: string;
  label: string;
  row: TileRow | null;
  /** Constraint whose result is this metric's status (none: informational value). */
  constraintId?: string;
  status?: EngStatus;
}

export function cells(a: MissionAnalysis): Cell[] {
  const b = a.budgets;
  const link = a.constraints.find((c) => c.id === "link-margin");
  const linkRow: TileRow =
    link?.actual && link.actual.provenance.fidelity !== "not-modelled"
      ? { key: "link", label: "Link margin", text: formatQuantity(link.actual), provenance: link.actual.provenance, raw: link.actual.value }
      : { key: "link", label: "Link margin", text: null, provenance: { fidelity: "not-modelled", sourceName: "No link result" }, raw: null, reason: link?.explanation };
  return [
    { key: "wet", label: "Wet mass", row: quantityRow("wet", "Wet mass", b.wetMassKg) },
    { key: "mass-margin", label: "Mass margin", row: scalarRow(a, "m", "Mass margin", b.massMarginFraction, formatFraction, "mass-launch-limit"), constraintId: "mass-launch-limit" },
    { key: "avg-power", label: "Avg power", row: quantityRow("avg", "Average power", b.averagePowerW) },
    { key: "peak-power", label: "Peak power", row: quantityRow("peak", "Peak power", b.peakPowerW), constraintId: "peak-power" },
    { key: "energy", label: "Energy margin", row: scalarRow(a, "e", "Energy margin", b.energyMarginFraction, formatFraction, "energy-closure"), constraintId: "energy-closure" },
    { key: "prop", label: "Propellant", row: quantityRow("prop", "Propellant", b.propellantMassKg) },
    { key: "dv", label: "Δv margin", row: scalarRow(a, "dv", "Δv margin", b.deltaVMarginKmPerS, (v) => `${formatNumber(v)} km/s`, "delta-v-margin"), constraintId: "delta-v-margin" },
    { key: "link", label: "Link margin", row: linkRow, constraintId: "link-margin" },
    { key: "data", label: "Data return", row: scalarRow(a, "d", "Downlink margin", b.dataMarginFraction, formatFraction, "data-return"), constraintId: "data-return" },
    { key: "storage", label: "Data buffer", row: null, constraintId: "data-buffer" },
    { key: "cost", label: "Cost", row: quantityRow("cost", "Estimated cost", b.estimatedCostUsd), constraintId: "budget" },
    { key: "science", label: "Science coverage", row: scalarRow(a, "s", "Coverage", a.science.coverageScore, (v) => `${formatNumber(v)} %`), constraintId: "science-mandatory-coverage" },
  ];
}

export const FEASIBILITY: Record<MissionAnalysis["feasibility"], EngStatus> = {
  feasible: "PASS",
  marginal: "WATCH",
  infeasible: "FAIL",
};

/**
 * Live engineering dashboard (front_design.md 5.1 bottom panel). Every value is the backend's
 * MissionAnalysis for the shown revision; a metric the engine does not model says so instead
 * of showing a number. While a newer revision is analysed the old values stay, marked STALE.
 */
export function EngineeringDashboard() {
  const analysis = useMissionStore((s) => s.analysis);
  const status = useMissionStore((s) => s.status);
  const designRevision = useMissionStore((s) => s.designRevision);
  const analysisRevision = useMissionStore((s) => s.analysisRevision);

  const current = analysis !== null && analysisRevision === designRevision;
  const freshness: EngStatus | null =
    status === "calculating" ? "ANALYSING" : analysis && !current ? "STALE" : null;
  const failed = analysis ? analysisFailed(analysis) : false;

  return (
    <section aria-labelledby="dashboard-heading" data-testid="engineering-dashboard" className="panel p-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 id="dashboard-heading" className="flex items-center gap-2 font-mono text-xs uppercase tracking-[0.2em] text-primary">
          <Gauge aria-hidden className="h-3.5 w-3.5" /> Live engineering
        </h2>
        <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
          {analysis ? (
            <span data-testid="dashboard-revision">
              Analysis of revision {analysisRevision} · design revision {designRevision}
            </span>
          ) : (
            <span>No analysis yet</span>
          )}
          {freshness ? <EngStatusChip status={freshness} testId="dashboard-freshness" /> : null}
          {analysis ? (
            <span className="inline-flex items-center gap-1">
              Overall <EngStatusChip status={failed ? "NOT MODELLED" : FEASIBILITY[analysis.feasibility]} testId="dashboard-feasibility" />
            </span>
          ) : null}
        </div>
      </div>
      <ul className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-3 xl:grid-cols-4">
        {(analysis ? cells(analysis) : PLACEHOLDER).map((cell) => {
          const constraint = analysis && cell.constraintId ? analysis.constraints.find((c) => c.id === cell.constraintId) : undefined;
          const st: EngStatus | null = !analysis
            ? status === "calculating"
              ? "ANALYSING"
              : null
            : failed
              ? "NOT MODELLED"
              : cell.constraintId
                ? constraintStatus(constraint)
                : null;
          const text = cell.row?.text ?? null;
          // a metric without a budget field shows its constraint's own measured value, if any
          const actual = constraint?.actual;
          const shown =
            text ??
            (cell.row === null && actual && actual.provenance.fidelity !== "not-modelled" && !failed
              ? formatQuantity(actual)
              : null);
          return (
            <li key={cell.key} data-testid={`dash-${cell.key}`} className="min-w-0 bg-surface px-3 py-2">
              <div className="flex items-center justify-between gap-1">
                <span className="truncate text-[11px] uppercase tracking-wider text-muted">{cell.label}</span>
                {st ? <EngStatusChip status={st} /> : null}
              </div>
              <p className={`mt-0.5 truncate font-mono text-sm tabular-nums ${current ? "text-foreground" : "text-muted"}`} title={cell.row?.reason ?? constraint?.explanation}>
                {shown ?? (analysis ? "NOT MODELLED" : MISSING)}
              </p>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

const PLACEHOLDER: Cell[] = [
  "Wet mass", "Mass margin", "Avg power", "Peak power", "Energy margin", "Propellant",
  "Δv margin", "Link margin", "Data return", "Data buffer", "Cost", "Science coverage",
].map((label) => ({ key: label.toLowerCase().replace(/[^a-z]+/g, "-"), label, row: null }));

const RAIL_KEYS = ["wet", "mass-margin", "energy", "dv", "link", "data", "cost", "science"];

/**
 * Persistent live-budget rail (design_update.md 6.1): the decision-critical budgets of the
 * current analysis, always visible at the bottom of the architect. A value that changed in a
 * confirmed analysis lifts in briefly; nothing animates before the engine answers.
 */
export function LiveBudgetRail() {
  const analysis = useMissionStore((s) => s.analysis);
  const status = useMissionStore((s) => s.status);
  const designRevision = useMissionStore((s) => s.designRevision);
  const analysisRevision = useMissionStore((s) => s.analysisRevision);
  const listRef = useRef<HTMLUListElement>(null);
  const shown = useRef<Record<string, string>>({});
  const current = analysis !== null && analysisRevision === designRevision;
  const failed = analysis ? analysisFailed(analysis) : false;
  const rail = analysis ? cells(analysis).filter((c) => RAIL_KEYS.includes(c.key)) : [];

  useEffect(() => {
    if (!current) return;
    for (const cell of rail) {
      const text = cell.row?.text ?? "";
      if (shown.current[cell.key] !== undefined && shown.current[cell.key] !== text) {
        emphasiseChange(listRef.current?.querySelector(`[data-rail='${cell.key}']`) as HTMLElement | null);
      }
      shown.current[cell.key] = text;
    }
  });

  const freshness: EngStatus | null = status === "calculating" ? "ANALYSING" : analysis && !current ? "STALE" : null;
  return (
    <div
      data-testid="budget-rail"
      className="sticky bottom-0 z-20 -mx-4 border-t border-border bg-background/90 px-4 py-2 backdrop-blur-md sm:-mx-6 sm:px-6"
    >
      <div className="flex items-center gap-3">
        <div className="hidden shrink-0 flex-col sm:flex">
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-accent-cyan">Live budgets</span>
          <span className="text-[10px] text-muted">rev {analysisRevision ?? "—"} / {designRevision}</span>
        </div>
        {analysis ? (
          <div tabIndex={0} role="region" aria-label="Live budgets (scrolls sideways)" className="min-w-0 flex-1 overflow-x-auto">
          <ul ref={listRef} className="flex gap-3">
            {rail.map((cell) => {
              const k = cell.constraintId ? analysis.constraints.find((c) => c.id === cell.constraintId) : undefined;
              const st = failed ? "NOT MODELLED" : cell.constraintId ? constraintStatus(k) : null;
              return (
                <li key={cell.key} data-rail={cell.key} className="min-w-[6.5rem] shrink-0">
                  <span className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted">
                    {cell.label}
                    {st && st !== "PASS" ? <EngStatusChip status={st} /> : null}
                  </span>
                  <span className={`readout block text-sm ${current ? "" : "text-muted"}`}>{cell.row?.text ?? (failed ? "NOT MODELLED" : MISSING)}</span>
                </li>
              );
            })}
          </ul>
          </div>
        ) : (
          <p className="flex-1 text-xs text-muted">{status === "calculating" ? "Analysing the design…" : "Budgets appear once the engine has analysed the design."}</p>
        )}
        <div className="flex shrink-0 items-center gap-2">
          {freshness ? <EngStatusChip status={freshness} /> : null}
          {analysis ? <EngStatusChip status={failed ? "NOT MODELLED" : FEASIBILITY[analysis.feasibility]} testId="rail-feasibility" /> : null}
          <button
            type="button"
            className="btn btn-tertiary min-h-8 px-2 text-xs"
            aria-label="Show all budgets"
            onClick={() => {
              useArchitectUi.getState().setMobileTab("budgets");
              requestAnimationFrame(() => document.getElementById("dashboard-heading")?.scrollIntoView({ block: "start" }));
            }}
          >
            <ChevronUp aria-hidden className="h-3.5 w-3.5" /> All
          </button>
        </div>
      </div>
    </div>
  );
}

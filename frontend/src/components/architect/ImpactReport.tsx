"use client";

import { ArrowRight, Loader2, RotateCcw, Sparkles } from "lucide-react";
import { useEffect, useRef } from "react";

import { formatFraction, formatNumber, formatQuantity, humanize, MISSING } from "@/lib/format";
import type { components } from "@/lib/api/schema";
import { emphasiseChange, enter } from "@/lib/motion/motion";
import { constraintStatus } from "@/lib/spacecraft/engineering-status";
import { useChangeStore } from "@/state/change-store";
import { useMissionStore, type MissionAnalysis } from "@/state/mission-store";
import { CATEGORY_ORDER, type CatalogComponent } from "./catalog-helpers";
import { undoLastChange } from "./component-actions";
import { EngStatusChip } from "./EngStatusChip";
import { shortName } from "./OptionCard";

type Quantity = components["schemas"]["Quantity"];

interface Row {
  key: string;
  label: string;
  before: string;
  after: string;
}

const q = (x: Quantity | null | undefined) => (x && x.provenance.fidelity !== "not-modelled" ? formatQuantity(x) : MISSING);
const f = (x: number | null | undefined) => (typeof x === "number" ? formatFraction(x) : MISSING);

/** Budget values, before and after, exactly as the backend returned them (no arithmetic). */
function budgetRows(a: MissionAnalysis, b: MissionAnalysis): Row[] {
  const rows: Row[] = [
    { key: "wet", label: "Wet mass", before: q(a.budgets.wetMassKg), after: q(b.budgets.wetMassKg) },
    { key: "mass-margin", label: "Mass margin", before: f(a.budgets.massMarginFraction), after: f(b.budgets.massMarginFraction) },
    { key: "avg-power", label: "Average power", before: q(a.budgets.averagePowerW), after: q(b.budgets.averagePowerW) },
    { key: "peak-power", label: "Peak power", before: q(a.budgets.peakPowerW), after: q(b.budgets.peakPowerW) },
    { key: "energy", label: "Energy margin", before: f(a.budgets.energyMarginFraction), after: f(b.budgets.energyMarginFraction) },
    { key: "dv", label: "Δv margin", before: a.budgets.deltaVMarginKmPerS == null ? MISSING : `${formatNumber(a.budgets.deltaVMarginKmPerS)} km/s`, after: b.budgets.deltaVMarginKmPerS == null ? MISSING : `${formatNumber(b.budgets.deltaVMarginKmPerS)} km/s` },
    { key: "data", label: "Downlink margin", before: f(a.budgets.dataMarginFraction), after: f(b.budgets.dataMarginFraction) },
    { key: "cost", label: "Estimated cost", before: q(a.budgets.estimatedCostUsd), after: q(b.budgets.estimatedCostUsd) },
    { key: "science", label: "Science coverage score", before: `${formatNumber(a.science.coverageScore)} %`, after: `${formatNumber(b.science.coverageScore)} %` },
  ];
  return rows.filter((r) => r.before !== r.after);
}

/**
 * Impact report (design_update.md 6.7): after a confirmed change, what changed in the design,
 * which budgets moved, which constraints changed status, which science requirements were
 * gained or lost and which subsystems are affected. Every value and explanation is the
 * backend's; the engine sends no separate impact narrative, which the report says.
 */
export function ImpactReport({ index }: { index: Map<string, CatalogComponent> }) {
  const applied = useChangeStore((s) => s.applied);
  const mission = useMissionStore((s) => s.mission);
  const designRevision = useMissionStore((s) => s.designRevision);
  const analysis = useMissionStore((s) => s.analysis);
  const previous = useMissionStore((s) => s.previousAnalysis);
  const analysisRevision = useMissionStore((s) => s.analysisRevision);
  const status = useMissionStore((s) => s.status);
  const ref = useRef<HTMLElement>(null);
  const valuesRef = useRef<HTMLDListElement>(null);
  const live = applied !== null && applied.revision === designRevision;
  const ready = live && analysis !== null && analysisRevision === applied.revision && previous !== null && previous.designRevision < applied.revision;

  useEffect(() => {
    if (live) enter(ref.current);
  }, [live, applied?.revision]);
  useEffect(() => {
    if (ready) emphasiseChange(valuesRef.current);
  }, [ready]);

  if (!live || !mission || !applied) return null;
  const component = index.get(applied.componentId);
  const replaced = applied.replacedId ? index.get(applied.replacedId) : undefined;
  const label = CATEGORY_ORDER.find((c) => c.category === applied.category)?.label ?? applied.category;
  const headline =
    applied.kind === "add" ? "Component installed" : applied.kind === "remove" ? "Component removed" : `${label} replaced`;
  const what =
    applied.kind === "replace"
      ? `${replaced ? shortName(replaced) : applied.replacedId} → ${component ? shortName(component) : applied.componentId}`
      : component
        ? shortName(component)
        : applied.componentId;

  let body: React.ReactNode;
  if (!ready) {
    body =
      status === "error" ? (
        <p className="text-sm text-accent-red">Analysis of revision {applied.revision} failed; no impact can be shown. Use Retry in the analysis status.</p>
      ) : (
        <p role="status" className="flex items-center gap-2 text-sm text-muted">
          <Loader2 aria-hidden className="h-4 w-4 animate-spin motion-reduce:animate-none" /> Analysing revision {applied.revision}… budgets update when the engine answers.
        </p>
      );
  } else {
    const rows = budgetRows(previous!, analysis!);
    const prevById = new Map(previous!.constraints.map((c) => [c.id, c]));
    const statusChanges = analysis!.constraints.filter((c) => {
      const p = prevById.get(c.id);
      return !p || p.status !== c.status;
    });
    const marginMoves = analysis!.constraints.filter((c) => {
      const p = prevById.get(c.id);
      return p && p.status === c.status && typeof p.marginFraction === "number" && typeof c.marginFraction === "number" && p.marginFraction !== c.marginFraction;
    });
    const before = new Set(previous!.science.missingRequirements);
    const after = new Set(analysis!.science.missingRequirements);
    const measurement = (id: string) =>
      mission.scienceObjectives.flatMap((o) => o.requiredMeasurements).find((m) => m.id === id)?.description ?? id;
    const gained = [...before].filter((id) => !after.has(id));
    const lost = [...after].filter((id) => !before.has(id));
    const subsystems = [...new Set([...statusChanges, ...marginMoves].flatMap((c) => c.impactedSubsystems ?? []))];
    const consequence = statusChanges[0];

    body = (
      <div className="space-y-3">
        <ol aria-label="Cause and effect" className="flex flex-wrap items-center gap-1.5 text-xs">
          <li className="rounded border border-accent-cyan/50 px-2 py-0.5 text-accent-cyan">{what}</li>
          <ArrowRight aria-hidden className="h-3.5 w-3.5 text-muted" />
          <li className="rounded border border-border px-2 py-0.5">{subsystems.length ? subsystems.map(humanize).join(", ") : label}</li>
          <ArrowRight aria-hidden className="h-3.5 w-3.5 text-muted" />
          <li className="rounded border border-border px-2 py-0.5">{rows.length ? rows.slice(0, 3).map((r) => r.label.toLowerCase()).join(", ") : "no budget change"}</li>
          {consequence ? (
            <>
              <ArrowRight aria-hidden className="h-3.5 w-3.5 text-muted" />
              <li className="rounded border border-border px-2 py-0.5">
                {consequence.label}: {prevById.get(consequence.id) ? constraintStatus(prevById.get(consequence.id)) : "new"} → {constraintStatus(consequence)}
              </li>
            </>
          ) : null}
        </ol>

        {rows.length > 0 ? (
          <dl ref={valuesRef} data-testid="impact-budgets" className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
            {rows.map((r) => (
              <div key={r.key} className="flex items-center justify-between gap-2 border-b border-border/50 py-0.5">
                <dt className="text-muted">{r.label}</dt>
                <dd className="readout text-right">
                  <span className="text-muted">{r.before}</span> <ArrowRight aria-hidden className="inline h-3 w-3" /> <span>{r.after}</span>
                </dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="text-sm text-muted">No budget value changed in the engine&apos;s analysis.</p>
        )}

        {statusChanges.length > 0 ? (
          <ul data-testid="impact-constraints" className="space-y-1 text-sm">
            {statusChanges.map((c) => {
              const p = prevById.get(c.id);
              return (
                <li key={c.id} className="space-y-0.5">
                  <span className="flex flex-wrap items-center gap-1.5">
                    <span className="font-medium">{c.label}</span>
                    {p ? <EngStatusChip status={constraintStatus(p)} /> : <span className="text-xs text-muted">new</span>}
                    <ArrowRight aria-hidden className="h-3 w-3" />
                    <EngStatusChip status={constraintStatus(c)} />
                  </span>
                  <span className="block text-xs text-muted">{c.explanation}</span>
                </li>
              );
            })}
          </ul>
        ) : null}
        {marginMoves.length > 0 ? (
          <p className="text-xs text-muted">
            Margins moved (same status):{" "}
            {marginMoves.map((c) => `${c.label} ${f(prevById.get(c.id)?.marginFraction)} → ${f(c.marginFraction)}`).join("; ")}.
          </p>
        ) : null}
        {gained.length || lost.length ? (
          <div className="text-sm">
            {gained.map((id) => (
              <p key={id} className="text-accent-green">Science requirement now covered: {measurement(id)}</p>
            ))}
            {lost.map((id) => (
              <p key={id} className="text-accent-amber">Science requirement no longer covered: {measurement(id)}</p>
            ))}
          </div>
        ) : null}
        <p className="text-[11px] text-muted">
          Values and explanations are the engine&apos;s analyses of revisions {previous!.designRevision} and {analysis!.designRevision}. The
          engine sends no separate impact narrative.
        </p>
      </div>
    );
  }

  return (
    <section ref={ref} aria-labelledby="impact-heading" aria-live="polite" data-testid="impact-report" className="panel is-active p-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 id="impact-heading" className="flex items-center gap-2 font-mono text-xs uppercase tracking-[0.2em] text-primary">
          <Sparkles aria-hidden className="h-3.5 w-3.5" /> Impact report · {headline}
        </h2>
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-muted">revision {applied.revision}</span>
          <button type="button" data-testid="undo-change" onClick={undoLastChange} className="btn btn-tertiary min-h-8 px-2 text-xs">
            <RotateCcw aria-hidden className="h-3.5 w-3.5" /> Undo
          </button>
          <button type="button" onClick={() => useChangeStore.getState().clearApplied()} className="btn btn-tertiary min-h-8 px-2 text-xs" aria-label="Dismiss impact report">
            Dismiss
          </button>
        </div>
      </div>
      <p className="mb-2 text-sm font-medium">{what}</p>
      {body}
    </section>
  );
}

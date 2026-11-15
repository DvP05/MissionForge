"use client";

import { ShieldAlert, ShieldCheck, ShieldQuestion } from "lucide-react";

import { evaluateGates, gateCounts } from "@/lib/spacecraft/gates";
import { useMissionStore } from "@/state/mission-store";

/** Top-bar readiness summary from the backend analysis of the current revision only. */
export function ReadinessSummary({ testId = "readiness-summary" }: { testId?: string }) {
  const analysis = useMissionStore((s) => s.analysis);
  const analysisRevision = useMissionStore((s) => s.analysisRevision);
  const designRevision = useMissionStore((s) => s.designRevision);
  const status = useMissionStore((s) => s.status);
  const base = "inline-flex items-center gap-1.5 border bg-[#232729]/80 px-2 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-wider";

  if (!analysis || analysisRevision !== designRevision) {
    return (
      <span data-testid={testId} className={`${base} border-border text-muted`}>
        <ShieldQuestion aria-hidden className="h-3.5 w-3.5" />
        {status === "calculating" ? "Readiness: analysing" : "Readiness: open the architect to analyse"}
      </span>
    );
  }
  const c = gateCounts(evaluateGates(analysis.constraints));
  const ready = analysis.missionReady;
  return (
    <span
      data-testid={testId}
      className={`${base} ${ready ? "border-accent-green/50 text-accent-green" : c.FAIL ? "border-accent-red/50 text-accent-red" : "border-accent-amber/50 text-accent-amber"}`}
    >
      {ready ? <ShieldCheck aria-hidden className="h-3.5 w-3.5" /> : <ShieldAlert aria-hidden className="h-3.5 w-3.5" />}
      {ready ? "Mission-ready" : c.FAIL ? `${c.FAIL} gate${c.FAIL > 1 ? "s" : ""} failing` : `${c.WATCH} gate${c.WATCH === 1 ? "" : "s"} to watch`}
    </span>
  );
}

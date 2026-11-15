"use client";

import { SlidersHorizontal } from "lucide-react";
import Link from "next/link";

import { EngStatusChip } from "@/components/architect/EngStatusChip";
import { LoadingState } from "@/components/common/States";
import { LaunchPanel } from "@/components/mission-control/LaunchPanel";
import { RobustnessLab } from "@/components/robustness/RobustnessLab";
import { useAnalysis } from "@/hooks/useAnalysis";
import { formatFraction, formatQuantity, humanize, MISSING } from "@/lib/format";
import { constraintStatus } from "@/lib/spacecraft/engineering-status";
import { evaluateGates, gateCounts } from "@/lib/spacecraft/gates";
import { useMissionStore } from "@/state/mission-store";

const VERDICT = { PASS: "GO", WATCH: "GO · WATCH", FAIL: "NO-GO", "NOT MODELLED": "NOT MODELLED", ANALYSING: "ANALYSING", STALE: "STALE" } as const;

/**
 * Readiness review (Stitch "Formal System Readiness Review"). Each gate is audited from the
 * backend constraint results of the current design revision: actual, limit and margin per
 * constraint with the engine's own explanation. GO requires every modelled constraint to pass;
 * NOT MODELLED is never a GO. Flight authorisation is the ordinary launch, which the backend
 * refuses for a hard failure.
 */
export function ReadinessReview() {
  const mission = useMissionStore((s) => s.mission);
  const analysis = useMissionStore((s) => s.analysis);
  const analysisRevision = useMissionStore((s) => s.analysisRevision);
  const status = useMissionStore((s) => s.status);
  useAnalysis();
  if (!mission) return <LoadingState label="Loading mission" />;
  const current = analysis !== null && analysisRevision === mission.designRevision;
  if (!analysis || !current) {
    return <LoadingState label={status === "error" ? "Analysis failed; open the architect to retry" : "Auditing the current design revision"} />;
  }
  const gates = evaluateGates(analysis.constraints);
  const counts = gateCounts(gates);
  const audited = gates.filter((g) => g.status !== "NOT MODELLED").length;

  return (
    <div className="space-y-6" data-testid="readiness-review">
      <section className="panel chamfer p-5">
        <p className="label-caps text-muted">
          Design revision {analysis.designRevision} · engine {analysis.engineVersion} · catalogue {analysis.catalogVersion}
        </p>
        <h2 className="mt-2 text-2xl font-bold uppercase tracking-wide sm:text-3xl">Formal readiness review — {mission.title}</h2>
        <p className="mt-2 max-w-3xl text-sm text-muted">
          Every gate below is the engine&apos;s constraint result for this exact revision. A gate is GO only when all of its
          modelled constraints pass; anything the engine does not model is reported as such, never as GO.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <span
            data-testid="readiness-verdict"
            className={`label-caps border px-2 py-1 ${analysis.missionReady ? "border-primary text-primary" : "border-accent-red text-accent-red"}`}
          >
            {analysis.missionReady ? "Engine verdict: mission-ready" : "Engine verdict: not mission-ready"}
          </span>
          <span className="label-caps text-muted">
            Gates audited {audited}/{gates.length} · {counts.PASS} go · {counts.WATCH} watch · {counts.FAIL} no-go
          </span>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_26rem]">
        <ol className="space-y-4">
          {gates.map((g, i) => (
            <li key={g.gate.id} data-testid={`review-gate-${g.gate.id}`} data-status={g.status} className="panel p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="flex items-center gap-2 text-lg font-semibold">
                  <span className="label-caps bg-elevated px-1.5 py-0.5 text-muted">Gate_{String(i + 1).padStart(2, "0")}</span>
                  {g.gate.label}
                </h3>
                <span className="flex items-center gap-2">
                  <span className="label-caps text-foreground">{VERDICT[g.status]}</span>
                  <EngStatusChip status={g.status} />
                </span>
              </div>
              {g.constraints.length === 0 ? (
                <p className="mt-2 text-sm text-muted">{g.gate.id === "compat" ? "No catalogue compatibility rule is broken." : "The engine does not model this gate."}</p>
              ) : (
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  {g.constraints.map((c) => (
                    <div key={c.id} className="border-l-2 border-primary bg-background-2 p-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="label-caps text-muted">{c.label}</span>
                        <EngStatusChip status={constraintStatus(c)} />
                      </div>
                      {c.status === "not-modelled" ? (
                        <p className="mt-1 text-xs text-muted">{c.explanation}</p>
                      ) : (
                        <>
                          <dl className="mt-1 grid grid-cols-3 gap-2 font-mono text-sm">
                            <div>
                              <dt className="label-caps text-faint">Actual</dt>
                              <dd className="truncate">{c.actual ? formatQuantity(c.actual) : MISSING}</dd>
                            </div>
                            <div>
                              <dt className="label-caps text-faint">Limit</dt>
                              <dd className="truncate">{c.limit ? formatQuantity(c.limit) : MISSING}</dd>
                            </div>
                            <div>
                              <dt className="label-caps text-faint">Margin</dt>
                              <dd className="truncate">{typeof c.marginFraction === "number" ? formatFraction(c.marginFraction) : MISSING}</dd>
                            </div>
                          </dl>
                          <p className="mt-1 text-xs text-muted">{c.explanation}</p>
                          {(c.impactedSubsystems ?? []).length ? (
                            <p className="mt-0.5 text-[11px] text-faint">Impacted: {(c.impactedSubsystems ?? []).map(humanize).join(", ")}</p>
                          ) : null}
                        </>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ol>
        <aside className="space-y-4">
          <div className="panel space-y-3 p-4">
            <h3 className="label-caps text-muted">Flight authorisation</h3>
            <p className="text-sm text-muted">
              Launching runs one deterministic, seeded simulation of this revision. The engine refuses to launch a design with a
              failing hard constraint (an experimental what-if is offered instead).
            </p>
            <LaunchPanel />
            <Link href={`/architect/${mission.missionId}`} className="btn btn-secondary w-full">
              <SlidersHorizontal aria-hidden className="h-4 w-4" /> Return to architect for optimisation
            </Link>
          </div>
          <RobustnessLab />
        </aside>
      </div>
    </div>
  );
}

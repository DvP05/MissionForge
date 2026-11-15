"use client";

import { ShieldCheck, Wrench } from "lucide-react";
import { useEffect, useRef } from "react";

import { formatFraction, formatQuantity, humanize, MISSING } from "@/lib/format";
import { settle } from "@/lib/motion/motion";
import { evaluateGates, gateCounts } from "@/lib/spacecraft/gates";
import { useArchitectUi } from "@/state/architect-ui-store";
import { useMissionStore } from "@/state/mission-store";
import { CATEGORY_ORDER } from "./catalog-helpers";
import { EngStatusChip } from "./EngStatusChip";

/**
 * Mission Readiness gate board (design_update.md 7.2). Each gate shows the backend status,
 * the driving constraint's actual value, limit and margin, the impacted subsystems and a repair
 * action that opens the relevant subsystem. Soft score never appears here: a hard failure is a
 * FAIL however good the score is.
 */
export function ReadinessBoard() {
  const analysis = useMissionStore((s) => s.analysis);
  const analysisRevision = useMissionStore((s) => s.analysisRevision);
  const designRevision = useMissionStore((s) => s.designRevision);
  const status = useMissionStore((s) => s.status);
  const listRef = useRef<HTMLUListElement>(null);
  const current = analysis !== null && analysisRevision === designRevision;

  // a confirmed analysis that changed a gate gets a short settle on that gate only
  const prevStatuses = useRef<Record<string, string>>({});
  const results = analysis ? evaluateGates(analysis.constraints) : [];
  useEffect(() => {
    if (!current) return;
    for (const r of results) {
      const before = prevStatuses.current[r.gate.id];
      if (before && before !== r.status) settle(listRef.current?.querySelector(`[data-gate='${r.gate.id}']`) as HTMLElement | null);
      prevStatuses.current[r.gate.id] = r.status;
    }
  });

  const counts = gateCounts(results);
  const open = (category: (typeof CATEGORY_ORDER)[number]["category"]) => {
    const ui = useArchitectUi.getState();
    ui.setCategory(category);
    ui.setMobileTab("build");
    document.getElementById("component-panel")?.scrollIntoView({ block: "start" });
  };

  return (
    <section aria-labelledby="readiness-heading" data-testid="readiness-board" className="panel p-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 id="readiness-heading" className="flex items-center gap-2 font-mono text-xs uppercase tracking-[0.2em] text-primary">
          <ShieldCheck aria-hidden className="h-3.5 w-3.5" /> Mission readiness gates
        </h2>
        {analysis ? (
          <p className="text-xs text-muted" data-testid="gate-counts">
            {counts.PASS} pass · {counts.WATCH} watch · {counts.FAIL} fail · {counts["NOT MODELLED"]} not modelled
            {!current ? (status === "calculating" ? " · analysing new revision" : " · from an earlier revision") : ""}
          </p>
        ) : null}
      </div>
      {!analysis ? (
        <p className="text-sm text-muted">{status === "calculating" ? "Analysing the design…" : "Gates appear once the engine has analysed the design."}</p>
      ) : (
        <ul ref={listRef} className="grid gap-2 sm:grid-cols-2">
          {results.map((r) => {
            const d = r.driver;
            const st = current ? r.status : status === "calculating" ? "ANALYSING" : "STALE";
            const repairLabel = CATEGORY_ORDER.find((c) => c.category === r.repair)?.label ?? humanize(r.repair);
            return (
              <li
                key={r.gate.id}
                data-gate={r.gate.id}
                data-testid={`gate-${r.gate.id}`}
                data-status={r.status}
                className={`rounded-lg border p-2.5 text-sm ${
                  r.status === "FAIL" ? "border-accent-red/50 bg-accent-red/[0.06]" : r.status === "WATCH" ? "border-accent-amber/50" : "border-border"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{r.gate.label}</span>
                  <EngStatusChip status={st} />
                </div>
                {d && d.status !== "not-modelled" ? (
                  <dl className="mt-1 grid grid-cols-3 gap-1 text-xs">
                    <div>
                      <dt className="text-muted">Actual</dt>
                      <dd className="readout truncate">{d.actual ? formatQuantity(d.actual) : MISSING}</dd>
                    </div>
                    <div>
                      <dt className="text-muted">Limit</dt>
                      <dd className="readout truncate">{d.limit ? formatQuantity(d.limit) : MISSING}</dd>
                    </div>
                    <div>
                      <dt className="text-muted">Margin</dt>
                      <dd className="readout truncate">{typeof d.marginFraction === "number" ? formatFraction(d.marginFraction) : MISSING}</dd>
                    </div>
                  </dl>
                ) : (
                  <p className="mt-1 text-xs text-muted">{d ? d.explanation : r.gate.id === "compat" ? "No catalogue rule is broken." : "The engine does not model this gate."}</p>
                )}
                {(r.status === "FAIL" || r.status === "WATCH") && d ? (
                  <div className="mt-1.5 space-y-1">
                    <p className="text-xs">{d.explanation}</p>
                    {(d.impactedSubsystems ?? []).length > 0 ? (
                      <p className="text-[11px] text-muted">Impacted: {(d.impactedSubsystems ?? []).map(humanize).join(", ")}</p>
                    ) : null}
                    {(d.suggestedActions ?? []).slice(0, 1).map((a) => (
                      <p key={a.actionId} className="text-[11px] text-muted">
                        Engine suggests: {a.label}. {a.expectedEffect}
                      </p>
                    ))}
                    <div className="flex flex-wrap gap-1.5">
                      <button type="button" data-testid={`gate-repair-${r.gate.id}`} onClick={() => open(r.repair)} className="btn btn-secondary min-h-8 px-2 text-xs">
                        <Wrench aria-hidden className="h-3.5 w-3.5" /> Open {repairLabel}
                      </button>
                      {r.gate.id === "comms" || r.gate.id === "science" ? (
                        <button
                          type="button"
                          data-testid={`gate-ops-${r.gate.id}`}
                          onClick={() => {
                            useArchitectUi.getState().setMobileTab("spacecraft");
                            requestAnimationFrame(() => document.getElementById("ops-heading")?.scrollIntoView({ block: "center" }));
                          }}
                          className="btn btn-tertiary min-h-8 px-2 text-xs"
                        >
                          Adjust operations plan
                        </button>
                      ) : null}
                    </div>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

import { Rocket } from "lucide-react";

import { ConstraintBadge } from "@/components/common/ConstraintBadge";
import { FidelityBadge } from "@/components/common/FidelityBadge";
import { ProvenancePopover } from "@/components/common/ProvenancePopover";
import { StatusPill } from "@/components/common/StatusPill";
import type { MissionAnalysis } from "@/state/mission-store";
import { countConstraintStatuses } from "@/state/selectors";
import { analysisProvenance } from "./tile-model";

const LABEL = { feasible: "Feasible", marginal: "Marginal", infeasible: "Infeasible" } as const;

/** Backend feasibility and mission-ready verdict. "Mission-ready" only when the backend says so. */
export function FeasibilityCard({
  analysis,
  changed,
  reason,
}: {
  analysis: MissionAnalysis | null;
  changed: boolean;
  reason: string;
}) {
  if (!analysis) {
    return (
      <section
        data-testid="budget-tile-feasibility"
        data-changed="false"
        aria-label="Feasibility"
        className="rounded-lg border border-border p-3"
      >
        <h3 className="text-sm font-semibold">Feasibility</h3>
        <p className="mt-2 flex items-center gap-2">
          <span className="text-lg font-semibold">—</span>
          <span data-testid="missing-reason" className="text-xs text-muted">
            {reason}
          </span>
        </p>
      </section>
    );
  }
  const counts = countConstraintStatuses(analysis);
  const provenance = analysisProvenance(analysis);
  return (
    <section
      data-testid="budget-tile-feasibility"
      data-changed={changed ? "true" : "false"}
      aria-label="Feasibility"
      className={`space-y-2 rounded-lg border p-3 ${changed ? "border-accent-cyan/70 bg-accent-cyan/5" : "border-border"}`}
    >
      <h3 className="text-sm font-semibold">Feasibility</h3>
      <div className="flex flex-wrap items-center gap-2">
        <span data-testid="feasibility-badge" className="text-lg font-semibold">
          {LABEL[analysis.feasibility]}
        </span>
        <span data-testid="mission-ready-badge">
          <StatusPill
            tone={analysis.missionReady ? "ok" : "warn"}
            icon={<Rocket aria-hidden className="h-3.5 w-3.5" />}
          >
            {analysis.missionReady ? "Mission-ready" : "Not mission-ready"}
          </StatusPill>
        </span>
        <FidelityBadge fidelity={provenance.fidelity} />
        <ProvenancePopover provenance={provenance} label="feasibility" />
      </div>
      <ul className="flex flex-wrap gap-3 text-xs text-muted" aria-label="Constraint tally">
        {(["fail", "warning", "pass", "not-modelled"] as const).map((s) => (
          <li key={s} className="inline-flex items-center gap-1.5">
            <ConstraintBadge status={s} />
            <span>{counts[s]}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

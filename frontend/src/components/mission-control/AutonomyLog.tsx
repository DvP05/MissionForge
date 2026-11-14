"use client";

import { StatusPill } from "@/components/common/StatusPill";
import { formatFraction, formatNumber, humanize } from "@/lib/format";
import { decisionDay, POLICY_LABEL, type AutonomyDecision } from "./authority";
import type { MissionRun } from "./playback";

function BeliefBars({ belief }: { belief: AutonomyDecision["belief"] }) {
  if (belief.hypotheses.length === 0) {
    return <p className="text-xs text-muted">No hypothesis model for this scenario (information gain 0).</p>;
  }
  return (
    <ul aria-label="Input belief" className="space-y-1">
      {belief.hypotheses.map((h) => (
        <li key={h.hypothesisId} className="grid grid-cols-[minmax(0,9rem)_1fr_3.5rem] items-center gap-2 text-xs">
          <span className="truncate">{humanize(h.hypothesisId)}</span>
          <span className="h-2 rounded bg-border">
            <span className="block h-2 rounded bg-accent-cyan" style={{ width: `${Math.round(h.probability * 100)}%` }} />
          </span>
          <span className="text-right font-mono">{formatFraction(h.probability)}</span>
        </li>
      ))}
    </ul>
  );
}

/** One decision: authority, input belief, the utility comparison, selection and reason. */
export function AutonomyEntry({ run, decision }: { run: MissionRun; decision: AutonomyDecision }) {
  const day = decisionDay(run, decision);
  const onboard = decision.decisionMaker === "onboard-policy";
  return (
    <li data-testid="autonomy-entry" data-maker={decision.decisionMaker} className="space-y-2 rounded-xl border border-border bg-surface p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill tone={onboard ? "warn" : "info"}>{onboard ? "Onboard autonomy" : "Ground control"}</StatusPill>
        <span className="text-xs text-muted">
          {day !== null ? `Day ${formatNumber(day)} · ` : ""}
          {POLICY_LABEL[decision.policy]} policy
        </span>
        <StatusPill tone={decision.selectedActionId ? "ok" : "neutral"}>
          {decision.selectedActionId ? "Observe" : "Hold"}
        </StatusPill>
      </div>
      <BeliefBars belief={decision.belief} />
      <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Candidate utilities (scrolls sideways)">
        <table className="w-full text-left text-xs">
          <caption className="sr-only">Candidate actions and their utilities</caption>
          <thead className="text-muted">
            <tr>
              <th scope="col" className="py-1 pr-3 font-medium">Candidate</th>
              <th scope="col" className="py-1 pr-3 font-medium">Utility</th>
              <th scope="col" className="py-1 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {decision.candidates.map((c) => (
              <tr key={c.actionId} className="border-t border-border/60">
                <td className="break-all py-1 pr-3 font-mono">{c.actionId}</td>
                <td className="py-1 pr-3 font-mono">{c.utility.toFixed(2)}</td>
                <td className="py-1">{c.feasible ? (c.actionId === decision.selectedActionId ? "Selected" : "Feasible") : c.rejectionReason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs">{decision.reason}</p>
    </li>
  );
}

/** Autonomy decisions up to the playback day (Task 6.5 audit log). */
export function AutonomyLog({ run, day }: { run: MissionRun; day: number }) {
  const log = run.autonomyLog ?? [];
  const shown = log.filter((d) => (decisionDay(run, d) ?? Infinity) <= day);
  return (
    <section data-testid="autonomy-log" aria-labelledby="autonomy-log-h" className="space-y-2">
      <h2 id="autonomy-log-h" className="text-base font-semibold">
        Autonomy log
      </h2>
      {shown.length === 0 ? (
        <p className="text-sm text-muted">
          {log.length === 0 ? "No autonomy decisions in this run." : "No observation decision yet at this mission day."}
        </p>
      ) : (
        <ol className="space-y-2">
          {shown.map((d, i) => (
            <AutonomyEntry key={i} run={run} decision={d} />
          ))}
        </ol>
      )}
      <p className="text-xs text-muted">
        One-step policy selector over planned observations (gameplay-estimate weights): an educational approximation,
        not a POMDP planner or flight software.
      </p>
    </section>
  );
}

"use client";

import { useEffect, useState } from "react";

import { StatusPill } from "@/components/common/StatusPill";
import { apiPost } from "@/lib/api-client";
import type { components } from "@/lib/api/schema";
import { CONFIDENCE_TONE, metricLine } from "./Counterfactual";

type RecommendData = components["schemas"]["RecommendData"];
type MissionRun = components["schemas"]["MissionRun"];

type Result = { runId: string } & ({ status: "error" } | { status: "ready"; data: RecommendData });
type State = { status: "loading" } | Result;

/**
 * Phase 4 <-> 6 join: the Mission Analyst (Task 6.8) asked about the design this run
 * actually flew (its immutable input snapshot), so the review shows engine-computed
 * counterfactuals instead of a placeholder. Read-only: a past run cannot be edited; the
 * player changes the current design in the Architect.
 */
export function RunCounterfactuals({ run }: { run: MissionRun }) {
  const [result, setResult] = useState<Result | null>(null);
  // A result for another run is stale: show loading until this run's answer arrives.
  const state: State = result && result.runId === run.runId ? result : { status: "loading" };

  useEffect(() => {
    const controller = new AbortController();
    const runId = run.runId;
    apiPost("/api/mission/recommend", { missionState: run.inputSnapshot, maxN: 3 }, { signal: controller.signal }).then(
      (r) => {
        if (controller.signal.aborted) return;
        setResult(r.ok && r.data ? { runId, status: "ready", data: r.data } : { runId, status: "error" });
      },
    );
    return () => controller.abort();
  }, [run.runId, run.inputSnapshot]);

  return (
    <div data-testid="run-analyst" className="space-y-3">
      {state.status === "error" ? (
        <p className="text-sm text-accent-amber">Counterfactuals are unavailable for this run&apos;s design.</p>
      ) : state.status === "loading" ? (
        <p role="status" className="text-sm text-muted">
          Re-running the engine on one-part changes to the flown design...
        </p>
      ) : state.data.recommendations.length === 0 ? (
        <p data-testid="run-analyst-none" className="text-sm text-muted">
          No single part swap would have improved the flown design.
        </p>
      ) : (
        <ol className="space-y-3">
          {state.data.recommendations.map((rec) => (
            <li
              key={rec.id}
              data-testid={`run-analyst-rec-${rec.id}`}
              className="space-y-2 rounded-xl border border-border bg-surface p-3 text-sm"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{rec.mutation.description}</span>
                <StatusPill tone={CONFIDENCE_TONE[rec.confidenceLabel]}>{rec.confidenceLabel} confidence</StatusPill>
              </div>
              <ul className="space-y-0.5 text-xs">
                {metricLine(rec, "scoreTotal", "Mission score", "number")}
                {metricLine(rec, "failedConstraints", "Hard failures", "number")}
                {metricLine(rec, "warningConstraints", "Watch items", "number")}
                {metricLine(rec, "returnedFraction", "Science returned", "fraction")}
                {metricLine(rec, "estimatedCostUsd", "Estimated cost", "musd")}
              </ul>
              {rec.tradeoffs.length > 0 ? <p className="text-xs text-muted">Trade-offs: {rec.tradeoffs.join(" ")}</p> : null}
            </li>
          ))}
        </ol>
      )}
      <p className="text-xs text-muted">
        Design-time analysis of the flown design (engine {run.engineVersion}), not a re-flown mission. Not AI-generated;
        based on gameplay-estimate parts.
      </p>
    </div>
  );
}

"use client";

import { Lightbulb } from "lucide-react";
import { useEffect, useState } from "react";

import { StatusPill } from "@/components/common/StatusPill";
import { ACTION_CLASS } from "@/components/common/States";
import { apiPost } from "@/lib/api-client";
import type { components } from "@/lib/api/schema";
import { formatFraction, formatNumber } from "@/lib/format";
import { useMissionStore, type ComponentCategory } from "@/state/mission-store";

type RecommendData = components["schemas"]["RecommendData"];
type Recommendation = components["schemas"]["Recommendation"];

/** Wait after an edit before asking (the analysis request goes first). */
const DEBOUNCE_MS = 400;

/** "architecture.<field>" -> catalogue category, for swap mutations (allow-list). */
const TARGET_CATEGORY: Record<string, ComponentCategory> = {
  "architecture.launchVehicleId": "launch",
  "architecture.busId": "bus",
  "architecture.propulsionId": "propulsion",
  "architecture.powerId": "power",
  "architecture.adcsId": "adcs",
  "architecture.communicationsId": "communications",
  "architecture.thermalId": "thermal",
  "architecture.cdhId": "cdh",
  "architecture.groundSegmentId": "ground",
};

const CONFIDENCE_TONE = { high: "ok", medium: "info", low: "neutral" } as const;

function metricLine(rec: Recommendation, key: string, label: string, kind: "number" | "fraction" | "musd") {
  const b = rec.metricBefore[key];
  const a = rec.metricAfter[key];
  if (b === undefined || a === undefined || b === a) return null;
  const show = (v: number) =>
    kind === "fraction" ? formatFraction(v) : kind === "musd" ? `${formatNumber(v / 1e6)} M USD` : formatNumber(v);
  return (
    <li key={key}>
      {label}: {show(b)} to {show(a)}
    </li>
  );
}

/** Applies an allow-listed mutation through the normal store actions (new revision). */
function applyRecommendation(rec: Recommendation) {
  const store = useMissionStore.getState();
  const m = rec.mutation;
  const str = (v: unknown) => (typeof v === "string" ? v : null);
  if (m.target === "architecture.instrumentIds") {
    const from = str(m.fromValue);
    const to = str(m.toValue);
    if (from) store.selectComponent("instrument", from);
    if (to) store.selectComponent("instrument", to);
  } else {
    const category = TARGET_CATEGORY[m.target];
    const to = str(m.toValue);
    if (!category || !to) return;
    store.selectComponent(category, to);
  }
  store.commitRevision();
}

/**
 * Mission Analyst (Task 6.8): up to three single changes that the backend engine shows
 * would improve this design, with before/after numbers and trade-offs. No AI text:
 * every number is a recomputed engine value. Applying one creates a new design revision.
 */
export function Counterfactual() {
  const missionId = useMissionStore((s) => s.mission?.missionId ?? null);
  const designRevision = useMissionStore((s) => s.designRevision);
  const [data, setData] = useState<RecommendData | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const mission = useMissionStore.getState().mission;
    if (!missionId || !mission) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      apiPost("/api/mission/recommend", { missionState: mission, maxN: 3 }, { signal: controller.signal }).then((r) => {
        if (controller.signal.aborted) return;
        if (useMissionStore.getState().designRevision !== mission.designRevision) return;
        if (r.ok && r.data && r.data.designRevision === mission.designRevision) {
          setData(r.data);
          setError(false);
        } else {
          setError(true);
        }
      });
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [missionId, designRevision]);

  const current = data !== null && data.designRevision === designRevision;

  return (
    <section aria-labelledby="analyst-title" data-testid="mission-analyst" className="space-y-3">
      <h2 id="analyst-title" className="flex items-center gap-2 text-sm font-semibold">
        <Lightbulb aria-hidden className="h-4 w-4 text-accent-amber" />
        Mission Analyst suggestions
      </h2>
      {error ? (
        <p className="text-sm text-accent-amber">Suggestions are unavailable for this revision.</p>
      ) : !current ? (
        <p role="status" className="text-sm text-muted">
          Testing single-part changes on the engine...
        </p>
      ) : data.recommendations.length === 0 ? (
        <p data-testid="analyst-none" className="text-sm text-muted">
          No single part swap improves this design right now. Try the Design Arena for bigger changes.
        </p>
      ) : (
        <ol className="space-y-3">
          {data.recommendations.map((rec) => (
            <li
              key={rec.id}
              data-testid={`analyst-rec-${rec.id}`}
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
              {rec.tradeoffs.length > 0 ? (
                <p className="text-xs text-muted">Trade-offs: {rec.tradeoffs.join(" ")}</p>
              ) : null}
              <button type="button" className={ACTION_CLASS} onClick={() => applyRecommendation(rec)}>
                Apply (new revision)
              </button>
            </li>
          ))}
        </ol>
      )}
      <p className="text-xs text-muted">
        Computed by re-running the engine on each one-part change. Not AI-generated; based on gameplay-estimate parts.
      </p>
    </section>
  );
}

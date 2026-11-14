"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiPost } from "@/lib/api-client";
import { useMissionStore, type MissionState } from "@/state/mission-store";
import type { GraphData, ImpactReport } from "./graph-model";

/** Wait after the last committed edit before asking for the graph (analysis goes first). */
export const GRAPH_DEBOUNCE_MS = 250;

export interface ImpactView {
  beforeRevision: number;
  afterRevision: number;
  report: ImpactReport;
}

export interface GraphState {
  data: GraphData | null;
  status: "idle" | "loading" | "error";
  impact: ImpactView | null;
}

/**
 * Stale-safe graph loader (same rules as useAnalysis): one POST /api/mission/graph per
 * committed revision; a response is applied only if its designRevision is still current.
 * After a successful load it also asks /api/mission/impact to explain the edit from the
 * previously shown revision, which drives the "Why did this change?" list.
 */
export function useArchitectureGraph(): GraphState & { retry: () => void } {
  const missionId = useMissionStore((s) => s.mission?.missionId ?? null);
  const designRevision = useMissionStore((s) => s.designRevision);
  const [state, setState] = useState<GraphState>({ data: null, status: "idle", impact: null });
  const [attempt, setAttempt] = useState(0);
  const lastShown = useRef<MissionState | null>(null);

  useEffect(() => {
    const mission = useMissionStore.getState().mission;
    if (!missionId || !mission) return;
    const requestRevision = mission.designRevision;
    const controller = new AbortController();
    const isCurrent = () =>
      !controller.signal.aborted && useMissionStore.getState().designRevision === requestRevision;

    const timer = setTimeout(() => {
      setState((s) => ({ ...s, status: "loading" }));
      apiPost("/api/mission/graph", { missionState: mission }, { signal: controller.signal }).then((result) => {
        if (!isCurrent()) return;
        const data = result.ok ? result.data : undefined;
        if (!data || data.designRevision !== requestRevision || data.missionId !== mission.missionId) {
          setState((s) => ({ ...s, status: "error" }));
          return;
        }
        const previous = lastShown.current;
        lastShown.current = mission;
        setState((s) => ({
          data,
          status: "idle",
          // Keep the last explanation until a newer one arrives.
          impact: s.impact && s.impact.afterRevision === requestRevision ? s.impact : null,
        }));
        if (
          !previous ||
          previous.missionId !== mission.missionId ||
          previous.designRevision >= requestRevision
        ) {
          return;
        }
        apiPost(
          "/api/mission/impact",
          { beforeMissionState: previous, afterMissionState: mission },
          { signal: controller.signal },
        ).then((impact) => {
          if (!isCurrent() || !impact.ok || !impact.data) return;
          const { beforeRevision, afterRevision, impact: report } = impact.data;
          if (afterRevision !== requestRevision) return;
          setState((s) => ({ ...s, impact: { beforeRevision, afterRevision, report } }));
        });
      });
    }, GRAPH_DEBOUNCE_MS);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [missionId, designRevision, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { ...state, retry };
}

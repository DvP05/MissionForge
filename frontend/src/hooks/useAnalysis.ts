"use client";

import { useCallback, useEffect, useState } from "react";

import { apiPost } from "@/lib/api-client";
import { useMissionStore } from "@/state/mission-store";

/**
 * Minimal backend analysis trigger (Task 3.3). Posts the committed MissionState
 * to POST /api/mission/validate whenever the design revision changes and hands
 * the result to the store, which drops it unless it matches the current
 * revision. Task 3.4 replaces this with the debounced, stale-safe hook; keep the
 * single call site and the `{ retry }` return shape.
 */
export function useAnalysis(): { retry: () => void } {
  const missionId = useMissionStore((s) => s.mission?.missionId ?? null);
  const designRevision = useMissionStore((s) => s.designRevision);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!missionId) return;
    const store = useMissionStore.getState();
    const mission = store.mission;
    if (!mission) return;
    if (
      attempt === 0 &&
      store.analysis &&
      store.analysisRevision === mission.designRevision &&
      store.analysis.missionId === mission.missionId
    ) {
      return;
    }
    const controller = new AbortController();
    store.setCalculating();
    apiPost("/api/mission/validate", { missionState: mission }, { signal: controller.signal }).then(
      (result) => {
        if (controller.signal.aborted) return;
        const state = useMissionStore.getState();
        // A non-aborted response that does not match the current mission/revision is an error
        // (never leave "calculating" forever).
        if (!(result.ok && result.data && state.applyAnalysis(result.data.analysis))) {
          state.setAnalysisError();
        }
      },
    );
    return () => {
      controller.abort();
      // An aborted request must not leave a stale "calculating" behind (unmount/remount).
      const s = useMissionStore.getState();
      if (s.status === "calculating") useMissionStore.setState({ status: s.analysis ? "stale" : "idle" });
    };
  }, [missionId, designRevision, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { retry };
}

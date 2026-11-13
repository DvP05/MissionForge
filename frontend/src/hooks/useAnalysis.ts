"use client";

import { useCallback, useEffect, useState } from "react";

import { apiPost } from "@/lib/api-client";
import { useMissionStore } from "@/state/mission-store";

/** Quiet period after the last committed edit before the backend is asked (Task 3.4). */
export const ANALYSIS_DEBOUNCE_MS = 150;

/**
 * Stale-safe backend analysis trigger. Every committed design revision schedules one
 * POST /api/mission/validate after a 150 ms debounce. A newer revision cancels the timer
 * and aborts the in-flight request; a response is applied only when its designRevision
 * equals the store's current revision (the store enforces the same rule again). On
 * failure the last good analysis stays in the store, so the UI can keep showing it
 * marked "stale" with a Retry. This is the only call site of the validate endpoint.
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
    const requestRevision = mission.designRevision;
    const controller = new AbortController();
    store.setCalculating();

    const timer = setTimeout(() => {
        apiPost("/api/mission/validate", { missionState: mission }, { signal: controller.signal }).then(
          (result) => {
            if (controller.signal.aborted) return;
            const state = useMissionStore.getState();
            // A response for a revision that is no longer current is dropped, never applied.
            if (state.designRevision !== requestRevision) return;
            const analysis = result.ok ? result.data?.analysis : undefined;
            if (!(analysis && analysis.designRevision === requestRevision && state.applyAnalysis(analysis))) {
              state.setAnalysisError();
            }
          },
        );
    }, ANALYSIS_DEBOUNCE_MS);

    return () => {
      clearTimeout(timer);
      controller.abort();
      // A cancelled request must not leave "calculating" behind (unmount/remount); a newer
      // effect run sets it again straight away.
      const s = useMissionStore.getState();
      if (s.status === "calculating") useMissionStore.setState({ status: s.analysis ? "stale" : "idle" });
    };
  }, [missionId, designRevision, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { retry };
}

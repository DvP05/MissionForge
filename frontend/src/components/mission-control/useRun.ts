"use client";

import { useEffect, useState } from "react";

import { loadRun, type RunLoad } from "@/state/run-store";

/** Loads a run by id: memory, browser cache, then the backend. */
export function useRun(runId: string): { state: RunLoad | null; retry: () => void } {
  const [result, setResult] = useState<{ runId: string; attempt: number; load: RunLoad } | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    loadRun(runId, controller.signal).then((load) => {
      if (!controller.signal.aborted) setResult({ runId, attempt, load });
    });
    return () => controller.abort();
  }, [runId, attempt]);

  const state = result && result.runId === runId && result.attempt === attempt ? result.load : null;
  return { state, retry: () => setAttempt((n) => n + 1) };
}

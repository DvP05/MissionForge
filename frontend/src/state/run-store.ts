import { create } from "zustand";

import { apiGet } from "@/lib/api-client";
import { cacheRun, isValidRunId, loadCachedRun, type RunData } from "@/lib/persistence/run-cache";

/** Client-side holder of immutable runs, keyed by runId. Never mutates a run. */
interface RunStoreState {
  runs: Record<string, RunData>;
  putRun: (data: RunData) => void;
}

export const useRunStore = create<RunStoreState>((set) => ({
  runs: {},
  putRun: (data) => {
    cacheRun(data);
    set((s) => ({ runs: { ...s.runs, [data.run.runId]: data } }));
  },
}));

export type RunLoad =
  | { kind: "ready"; data: RunData }
  | { kind: "not-found" }
  | { kind: "error"; message: string };

/** Memory, then browser cache, then GET /api/mission/run/{runId}. */
export async function loadRun(runId: string, signal?: AbortSignal): Promise<RunLoad> {
  if (!isValidRunId(runId)) return { kind: "not-found" };
  const inMemory = useRunStore.getState().runs[runId];
  if (inMemory) return { kind: "ready", data: inMemory };
  const cached = loadCachedRun(runId);
  if (cached) {
    useRunStore.setState((s) => ({ runs: { ...s.runs, [runId]: cached } }));
    return { kind: "ready", data: cached };
  }
  const res = await apiGet("/api/mission/run/{run_id}", { pathParams: { run_id: runId }, signal });
  if (res.ok && res.data) {
    useRunStore.getState().putRun(res.data);
    return { kind: "ready", data: res.data };
  }
  if (res.error?.code === "RUN_NOT_FOUND" || res.httpStatus === 404) return { kind: "not-found" };
  if (res.error?.code === "ABORTED") return { kind: "error", message: "Request cancelled." };
  return { kind: "error", message: res.error?.message ?? "The run could not be loaded." };
}

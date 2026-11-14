"use client";

import { ErrorState, LoadingState, NotFoundState } from "@/components/common/States";
import type { RunData } from "@/lib/persistence/run-cache";
import { useRun } from "./useRun";

/** Resolves a run id (cache, then backend) and renders loading / not-found / error states. */
export function RunGate({ runId, children }: { runId: string; children: (data: RunData) => React.ReactNode }) {
  const { state, retry } = useRun(runId);
  if (!state) return <LoadingState label="Loading run" />;
  if (state.kind === "not-found") {
    return <NotFoundState title="Run not found" message="No simulation run with this ID exists in this browser or on the server." />;
  }
  if (state.kind === "error") return <ErrorState title="Run unavailable" message={state.message} onRetry={retry} />;
  return <>{children(state.data)}</>;
}

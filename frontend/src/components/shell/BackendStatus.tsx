"use client";

import { WifiOff } from "lucide-react";

import { useBackendHealth } from "@/components/shell/BackendHealth";

export function BackendStatus() {
  const { state } = useBackendHealth();

  const dot =
    state.kind === "online"
      ? "bg-accent-cyan"
      : state.kind === "offline"
        ? "bg-accent-amber"
        : "bg-muted";

  const label =
    state.kind === "online"
      ? `Engine ${state.health.engineVersion}`
      : state.kind === "offline"
        ? "Backend offline"
        : "Connecting to backend";

  return (
    <span
      data-testid="backend-status"
      role="status"
      title={state.kind === "offline" ? state.message : undefined}
      className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 font-mono text-xs text-foreground"
    >
      <span aria-hidden className={`h-2 w-2 rounded-full ${dot}`} />
      {label}
    </span>
  );
}

/** Persistent banner shown while the Python engine cannot be reached. */
export function OfflineBanner() {
  const { state, retry } = useBackendHealth();
  if (state.kind !== "offline") return null;
  return (
    <div
      data-testid="offline-banner"
      role="alert"
      className="flex flex-wrap items-center gap-3 border-b border-accent-amber/50 bg-accent-amber/10 px-4 py-2 text-sm text-accent-amber sm:px-6"
    >
      <WifiOff aria-hidden className="h-4 w-4 shrink-0" />
      <span className="min-w-0 flex-1">
        Backend unreachable. Analysis, templates and validation need the Python engine; saved
        missions can still be opened.
      </span>
      <button
        type="button"
        onClick={retry}
        className="min-h-9 rounded-md border border-accent-amber/60 px-3 text-xs font-medium hover:bg-accent-amber/10"
      >
        Retry
      </button>
    </div>
  );
}

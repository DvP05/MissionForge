"use client";

import { useEffect, useState } from "react";

import { apiGet } from "@/lib/api-client";
import type { components } from "@/lib/api/schema";

type Health = components["schemas"]["HealthData"];
type State =
  | { kind: "loading" }
  | { kind: "online"; health: Health }
  | { kind: "offline"; message: string };

export function BackendStatus() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    apiGet<Health>("/api/health").then((result) => {
      if (cancelled) return;
      if (result.ok && result.data) {
        setState({ kind: "online", health: result.data });
      } else {
        setState({
          kind: "offline",
          message: result.error?.message ?? "Backend unavailable",
        });
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

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

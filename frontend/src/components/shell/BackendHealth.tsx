"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

import { apiGet, type DataOf } from "@/lib/api-client";

type HealthResponse = Awaited<ReturnType<typeof apiGet<"/api/health">>>;
export type Health = DataOf<HealthResponse>;

export type HealthState =
  | { kind: "loading" }
  | { kind: "online"; health: Health }
  | { kind: "offline"; message: string };

interface HealthContextValue {
  state: HealthState;
  retry: () => void;
}

const HealthContext = createContext<HealthContextValue | null>(null);

export function BackendHealthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<HealthState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    apiGet("/api/health", { signal: controller.signal }).then((result) => {
      if (controller.signal.aborted) return;
      if (result.ok && result.data) {
        setState({ kind: "online", health: result.data });
      } else {
        setState({
          kind: "offline",
          message: result.error?.message ?? "Backend unavailable",
        });
      }
    });
    return () => controller.abort();
  }, [attempt]);

  const retry = useCallback(() => {
    setState({ kind: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  return <HealthContext.Provider value={{ state, retry }}>{children}</HealthContext.Provider>;
}

export function useBackendHealth(): HealthContextValue {
  const value = useContext(HealthContext);
  if (!value) throw new Error("useBackendHealth must be used inside BackendHealthProvider");
  return value;
}

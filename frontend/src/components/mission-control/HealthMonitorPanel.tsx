"use client";

import { useState } from "react";

import { apiPost } from "@/lib/api-client";
import type { RunData } from "@/lib/persistence/run-cache";

type Result =
  | { kind: "idle" }
  | { kind: "running" }
  | { kind: "ready"; anomalies: { severity: string; explanation: string }[]; disclaimer: string }
  | { kind: "error"; message: string };

export function HealthMonitorPanel({ data }: { data: RunData }) {
  const [result, setResult] = useState<Result>({ kind: "idle" });
  const telemetry = data.run.telemetry.filter((sample) => sample.channel === "pointing_error_deg");

  const analyze = async () => {
    setResult({ kind: "running" });
    const response = await apiPost("/api/mission/health-monitor", {
      telemetry,
      config: {
        channel: "pointing_error_deg",
        unit: "deg",
        expected: 0,
        warn: 0.5,
        crit: 1.5,
        persistenceK: 2,
        hardLimit: 3,
        lam: 0.4,
        rationale: "Explainable pointing-error teaching detector.",
      },
    });
    if (!response.ok || !response.data) {
      setResult({ kind: "error", message: response.error?.message ?? "Health analysis failed." });
      return;
    }
    setResult({ kind: "ready", anomalies: response.data.anomalies, disclaimer: response.data.disclaimer });
  };

  return (
    <section aria-labelledby="health-monitor-heading" className="space-y-3 rounded-lg border border-border p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="health-monitor-heading" className="text-sm font-semibold">M15 spacecraft health monitor</h2>
        <span className="text-xs text-muted">Educational detector</span>
      </div>
      <p className="text-xs text-muted">
        Analyze the recorded pointing-error telemetry with a transparent EWMA baseline. The detector never changes
        the mission run.
      </p>
      <button
        type="button"
        onClick={() => void analyze()}
        disabled={result.kind === "running" || telemetry.length === 0}
        className="min-h-10 rounded-lg border border-accent-cyan/60 px-3 text-sm text-accent-cyan disabled:opacity-50"
      >
        {result.kind === "running" ? "Analyzing…" : "Analyze telemetry"}
      </button>
      {telemetry.length === 0 ? <p className="text-xs text-muted">No pointing-error telemetry is available.</p> : null}
      {result.kind === "error" ? <p role="alert" className="text-sm text-accent-amber">{result.message}</p> : null}
      {result.kind === "ready" ? (
        <div className="space-y-2">
          <p className="text-sm">{result.anomalies.length} anomalies detected.</p>
          {result.anomalies.length > 0 ? (
            <ul className="space-y-2 text-sm">
              {result.anomalies.map((anomaly, index) => (
                <li key={`${anomaly.severity}-${index}`} className="rounded-lg border border-border p-2">
                  <span className="font-medium">{anomaly.severity}</span>: {anomaly.explanation}
                </li>
              ))}
            </ul>
          ) : null}
          <p className="text-xs text-muted">{result.disclaimer}</p>
        </div>
      ) : null}
    </section>
  );
}

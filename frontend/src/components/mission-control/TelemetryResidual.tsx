"use client";

import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, XAxis, YAxis } from "recharts";

import { StatusPill } from "@/components/common/StatusPill";
import { apiPost } from "@/lib/api-client";
import type { components } from "@/lib/api/schema";
import { formatNumber, humanize } from "@/lib/format";
import type { MissionRun } from "./playback";

type HealthReport = components["schemas"]["HealthReport"];
type Result = { runId: string } & ({ status: "ready"; report: HealthReport } | { status: "error" });

const CATEGORY = {
  "power-thermal": "Power / thermal",
  "attitude-pointing": "Attitude / pointing",
  "comms-data": "Comms / data",
  propulsion: "Propulsion",
} as const;

/**
 * Task 6.7: transparent health monitor. The backend compares the run's telemetry with the
 * nominal model (same design and seed, no anomalies) and applies EWMA + persistence rules.
 * ``day`` limits what is shown to the playback position (null = whole run, for review).
 */
export function TelemetryResidual({
  run,
  day,
  showHeading = true,
}: {
  run: MissionRun;
  day: number | null;
  showHeading?: boolean;
}) {
  const [result, setResult] = useState<Result | null>(null);
  const current = result && result.runId === run.runId ? result : null;

  useEffect(() => {
    const controller = new AbortController();
    const runId = run.runId;
    apiPost("/api/mission/health", { run }, { signal: controller.signal }).then((r) => {
      if (controller.signal.aborted) return;
      setResult(r.ok && r.data ? { runId, status: "ready", report: r.data } : { runId, status: "error" });
    });
    return () => controller.abort();
  }, [run]);

  const upTo = (d: number) => day === null || d <= day;

  return (
    <section data-testid="health-monitor" aria-label="Health monitor" className="space-y-3">
      {showHeading ? <h2 className="text-base font-semibold">Health monitor</h2> : null}
      {current === null ? (
        <p role="status" className="text-sm text-muted">
          Comparing telemetry with the nominal model...
        </p>
      ) : current.status === "error" ? (
        <p className="text-sm text-accent-amber">The health monitor is unavailable for this run.</p>
      ) : (
        <>
          {(() => {
            const findings = current.report.findings.filter((f) => upTo(f.anomaly.windowStart));
            return findings.length === 0 ? (
              <p data-testid="health-none" className="text-sm text-muted">
                No telemetry departs from the nominal model{day === null ? "" : " so far"}.
              </p>
            ) : (
              <ul className="space-y-2">
                {findings.map((f, i) => (
                  <li key={i} data-testid="health-finding" className="space-y-1 rounded-xl border border-border bg-surface p-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusPill tone={f.anomaly.severity === "critical" ? "danger" : "warn"}>{f.anomaly.severity}</StatusPill>
                      <span className="font-medium">{humanize(f.anomaly.channel)}</span>
                      <span className="text-xs text-muted">
                        day {formatNumber(f.anomaly.windowStart)}–{formatNumber(f.anomaly.windowEnd)}
                      </span>
                      {f.likelyFalsePositive ? <StatusPill tone="neutral">likely false positive</StatusPill> : null}
                    </div>
                    <p className="text-xs">{f.anomaly.explanation}</p>
                    <p className="text-xs text-muted">{f.explanation}</p>
                  </li>
                ))}
              </ul>
            );
          })()}
          <div className="grid gap-3 md:grid-cols-2">
            {current.report.channels.map((c) => {
              const pts = c.points.filter((p) => upTo(p.missionDay));
              return (
                <figure key={c.config.channel} data-testid={`health-channel-${c.config.channel}`} className="min-w-0 space-y-1 rounded-xl border border-border p-3">
                  <figcaption className="text-xs">
                    <span className="font-medium">{humanize(c.config.channel)}</span> · {CATEGORY[c.category]} · warn{" "}
                    {formatNumber(c.config.warn)} / crit {formatNumber(c.config.crit)} {c.config.unit}, k {c.config.persistenceK}, λ{" "}
                    {formatNumber(c.config.lam)}
                  </figcaption>
                  <LineChart width={320} height={120} data={pts} className="max-w-full" accessibilityLayer>
                    <CartesianGrid stroke="#243044" strokeDasharray="3 3" />
                    <XAxis dataKey="missionDay" type="number" domain={["dataMin", "dataMax"]} tick={{ fill: "#8fa0b8", fontSize: 10 }} />
                    <YAxis tick={{ fill: "#8fa0b8", fontSize: 10 }} width={44} domain={["auto", "auto"]} />
                    <Line dataKey="observed" name="Raw" stroke="#22d3ee" dot={false} isAnimationActive={false} />
                    <Line dataKey="expected" name="Nominal model" stroke="#8fa0b8" strokeDasharray="4 3" dot={false} isAnimationActive={false} />
                    <Line dataKey="ewma" name="EWMA residual" stroke="#fbbf24" dot={false} isAnimationActive={false} />
                    <ReferenceLine y={0} stroke="#243044" />
                  </LineChart>
                  <p className="text-xs text-muted">
                    Solid: raw · dashed: nominal model · amber: EWMA residual. Persistence now{" "}
                    {pts.length ? pts[pts.length - 1].persistence : 0}.
                  </p>
                </figure>
              );
            })}
          </div>
          <ul className="list-disc space-y-0.5 pl-5 text-xs text-muted">
            {current.report.assumptions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

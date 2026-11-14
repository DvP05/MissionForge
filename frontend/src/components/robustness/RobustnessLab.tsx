"use client";

import { Dices, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { FidelityBadge } from "@/components/common/FidelityBadge";
import { StatusPill } from "@/components/common/StatusPill";
import { ACTION_CLASS } from "@/components/common/States";
import { apiPost } from "@/lib/api-client";
import type { components } from "@/lib/api/schema";
import { formatFraction, formatNumber } from "@/lib/format";
import { useMissionStore } from "@/state/mission-store";

type RobustnessResult = components["schemas"]["RobustnessResult"];

/** Mirrors backend DEFAULT_SAMPLES / MAX_SAMPLES (routes/robustness.py, domain/uncertainty). */
const SAMPLE_OPTIONS = [100, 250, 1000] as const;

const METRIC_LABEL: Record<string, string> = {
  wetMassKg: "Wet mass",
  deltaVMarginKmPerS: "Delta-v margin",
  energyMarginFraction: "Energy margin",
  dataMarginFraction: "Data margin",
  returnedFraction: "Science returned",
  scienceCoverageScore: "Science coverage score",
  scoreTotal: "Mission score",
};

type Run =
  | { kind: "idle" }
  | { kind: "running" }
  | { kind: "done"; result: RobustnessResult; revision: number }
  | { kind: "error"; message: string };

function show(value: number | null, unit: string): string {
  // R38: null = undefined in every sample (e.g. no margin defined) - never a fake 0.
  if (value === null) return "— (not defined)";
  return unit === "fraction" ? formatFraction(value) : `${formatNumber(value)} ${unit}`;
}

/**
 * Robustness lab (Task 6.3): re-runs the backend engine on seeded, perturbed copies of the
 * current design and shows how often it stays feasible. Every number is from the backend.
 */
export function RobustnessLab() {
  const mission = useMissionStore((s) => s.mission);
  const analysis = useMissionStore((s) => s.analysis);
  const [samples, setSamples] = useState<(typeof SAMPLE_OPTIONS)[number]>(250);
  const [run, setRun] = useState<Run>({ kind: "idle" });
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);
  if (!mission) return null;

  const label = (id: string) => analysis?.constraints.find((c) => c.id === id)?.label ?? id;

  const execute = async () => {
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    const revision = mission.designRevision;
    setRun({ kind: "running" });
    const response = await apiPost(
      "/api/mission/robustness",
      { missionState: mission, samples },
      { signal: abort.signal, timeoutMs: 30_000 },
    );
    if (abort.signal.aborted) return;
    if (response.ok && response.data) setRun({ kind: "done", result: response.data.result, revision });
    else setRun({ kind: "error", message: response.error?.message ?? "The robustness run failed." });
  };

  const result = run.kind === "done" ? run.result : null;
  const outdated = run.kind === "done" && run.revision !== mission.designRevision;

  return (
    <section
      aria-labelledby="robustness-title"
      data-testid="robustness-lab"
      className="space-y-4 rounded-xl border border-border bg-surface/40 p-4"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h2 id="robustness-title" className="flex items-center gap-2 text-lg font-semibold">
            <Dices aria-hidden className="h-5 w-5 text-accent-cyan" />
            Robustness lab
          </h2>
          <p className="max-w-3xl text-sm text-muted">
            Real parts never match the datasheet exactly. This re-checks your current design many times with
            engine performance, masses, solar output, battery capacity, antenna losses and ground contacts nudged
            at random, and reports how often it still works.
          </p>
        </div>
        <FidelityBadge fidelity="gameplay-estimate" />
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm">
          Samples
          <select
            data-testid="robustness-samples"
            value={samples}
            onChange={(e) => setSamples(Number(e.target.value) as (typeof SAMPLE_OPTIONS)[number])}
            className="min-h-11 rounded-lg border border-border bg-surface px-3"
          >
            {SAMPLE_OPTIONS.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          data-testid="robustness-run"
          onClick={execute}
          disabled={run.kind === "running"}
          className={`${ACTION_CLASS} gap-2 disabled:opacity-50`}
        >
          <Play aria-hidden className="h-4 w-4" />
          {run.kind === "running" ? "Running..." : `Run on revision ${mission.designRevision}`}
        </button>
        {outdated ? (
          <StatusPill tone="warn" testId="robustness-outdated">
            Result is for revision {run.revision}; run again for the current design
          </StatusPill>
        ) : null}
      </div>

      {run.kind === "error" ? (
        <p role="alert" className="text-sm text-red-300">
          {run.message}
        </p>
      ) : null}

      {result ? (
        <div data-testid="robustness-result" className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-border bg-surface p-4">
              <p className="text-xs uppercase tracking-wide text-muted">Still feasible</p>
              <p data-testid="robustness-probability" className="mt-1 text-3xl font-semibold">
                {formatFraction(result.probabilityFeasible)}
              </p>
              <p className="text-xs text-muted">
                of {result.samples} samples (no hard constraint failed)
              </p>
            </div>
            <div className="rounded-xl border border-border bg-surface p-4">
              <p className="text-xs uppercase tracking-wide text-muted">95 % confidence range</p>
              <p data-testid="robustness-interval" className="mt-1 text-xl font-semibold">
                {formatFraction(result.feasibilityWilson95[0])} to {formatFraction(result.feasibilityWilson95[1])}
              </p>
              <p className="text-xs text-muted">Wilson interval; more samples give a narrower range.</p>
            </div>
            <div className="rounded-xl border border-border bg-surface p-4">
              <p className="text-xs uppercase tracking-wide text-muted">Most common hard failures</p>
              {Object.keys(result.failureCounts).length === 0 ? (
                <p className="mt-1 text-sm">None in this run.</p>
              ) : (
                <ul data-testid="robustness-failures" className="mt-1 space-y-1 text-sm">
                  {Object.entries(result.failureCounts)
                    .slice(0, 4)
                    .map(([id, count]) => (
                      <li key={id}>
                        {label(id)}: {count} of {result.samples}
                      </li>
                    ))}
                </ul>
              )}
            </div>
          </div>

          <div className="overflow-x-auto rounded-xl border border-border" tabIndex={0} role="region" aria-label="Robustness metrics table (scrolls sideways)">
            <table className="w-full min-w-[32rem] text-left text-sm" data-testid="robustness-metrics">
              <caption className="sr-only">Spread of key results across samples</caption>
              <thead className="bg-surface text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="px-3 py-2 font-medium">Result</th>
                  <th scope="col" className="px-3 py-2 font-medium">Low (10th percentile)</th>
                  <th scope="col" className="px-3 py-2 font-medium">Typical (median)</th>
                  <th scope="col" className="px-3 py-2 font-medium">High (90th percentile)</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(result.metrics).map(([key, q]) => (
                  <tr key={key} className="border-t border-border">
                    <td className="px-3 py-2">{METRIC_LABEL[key] ?? key}</td>
                    <td className="px-3 py-2 font-mono text-xs">{show(q.p10, q.unit)}</td>
                    <td className="px-3 py-2 font-mono text-xs">{show(q.median, q.unit)}</td>
                    <td className="px-3 py-2 font-mono text-xs">{show(q.p90, q.unit)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <details className="rounded-xl border border-border bg-surface p-4 text-sm">
            <summary className="cursor-pointer font-medium">Assumptions ({result.assumptions.length})</summary>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-muted">
              {result.assumptions.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-muted">
              Seed {result.seed}, profile {result.profileVersion}. Same design and seed always give the same result.
            </p>
          </details>
          <p data-testid="robustness-disclaimer" className="text-xs text-muted">
            {result.disclaimer}
          </p>
        </div>
      ) : null}
    </section>
  );
}

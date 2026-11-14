"use client";

import { CircleAlert, Copy, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useCatalog } from "@/components/architect/useCatalog";
import { ErrorState, LoadingState } from "@/components/common/States";
import { apiPost } from "@/lib/api-client";
import type { components } from "@/lib/api/schema";
import { useMissionStore, type ComponentCategory } from "@/state/mission-store";
import { AlternativeCard, withComponent, type Alternative } from "./AlternativeCard";
import { CompareTable } from "./CompareTable";

type TradeResult = components["schemas"]["TradeStudyResult"];

/** Mirrors the backend limit (POST /api/mission/trade-study accepts 1 to 3 alternatives). */
export const MAX_ALTERNATIVES = 3;
const LABELS = ["A", "B", "C"];

type Run =
  | { kind: "idle" }
  | { kind: "running" }
  | { kind: "done"; result: TradeResult; labels: string[]; version: number }
  | { kind: "error"; message: string };

function describeFailure(
  error: { message: string; details?: { [key: string]: unknown } | null } | null | undefined,
  labels: string[],
): string {
  const base = error?.message ?? "The trade study could not be run.";
  const design = error?.details?.design as { role?: string; index?: number | null } | undefined;
  if (design?.role === "base") return `Baseline: ${base}`;
  if (design?.role === "alternative" && typeof design.index === "number") {
    return `Alternative ${labels[design.index] ?? design.index + 1}: ${base}`;
  }
  return base;
}

/**
 * Compare the saved baseline with up to three alternative designs (F-019). The baseline is
 * read from the store and never edited here; alternatives are client-side copies kept in
 * component state only (not saved, lost on reload). All numbers come from the trade-study API.
 */
export function CompareView() {
  const mission = useMissionStore((s) => s.mission);
  const { catalog, retry: retryCatalog } = useCatalog();
  const [alternatives, setAlternatives] = useState<Alternative[]>([]);
  // Bumped on every alternative edit; a finished run is "out of date" when it lags behind.
  const [version, setVersion] = useState(0);
  const [run, setRun] = useState<Run>({ kind: "idle" });
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);

  if (!mission) return <LoadingState label="Loading mission" />;
  if (catalog.kind === "loading") return <LoadingState label="Loading component catalogue" />;
  if (catalog.kind === "error") {
    return <ErrorState title="Component catalogue unavailable" message={catalog.message} onRetry={retryCatalog} />;
  }

  const edited = (next: Alternative[]) => {
    setAlternatives(next);
    setVersion((v) => v + 1);
  };

  const add = () => {
    const label = LABELS.find((l) => !alternatives.some((a) => a.label === l));
    if (!label || alternatives.length >= MAX_ALTERNATIVES) return;
    edited([...alternatives, { label, mission: structuredClone(mission) }]);
  };

  const change = (label: string, category: ComponentCategory, id: string) =>
    edited(alternatives.map((a) => (a.label === label ? { ...a, mission: withComponent(a.mission, category, id) } : a)));

  const remove = (label: string) => edited(alternatives.filter((a) => a.label !== label));

  const execute = async () => {
    if (alternatives.length === 0 || run.kind === "running") return;
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    const labels = alternatives.map((a) => a.label);
    const startedAt = version;
    setRun({ kind: "running" });
    const result = await apiPost(
      "/api/mission/trade-study",
      { baseMissionState: mission, alternatives: alternatives.map((a) => a.mission) },
      { signal: abort.signal },
    );
    if (abort.signal.aborted) return;
    if (result.ok && result.data) {
      setRun({ kind: "done", result: result.data, labels, version: startedAt });
    } else {
      setRun({ kind: "error", message: describeFailure(result.error, labels) });
    }
  };

  const atLimit = alternatives.length >= MAX_ALTERNATIVES;
  const stale = run.kind === "done" && run.version !== version;

  return (
    <div className="space-y-4" data-testid="compare-view">
      <section aria-labelledby="compare-heading" className="space-y-2">
        <h2 id="compare-heading" className="text-lg font-semibold">
          Compare designs
        </h2>
        <p className="text-sm text-muted">
          The baseline (revision {mission.designRevision}) stays exactly as saved. Alternatives are copies you can
          change here; they are not saved and disappear when you reload this page. All figures come from the
          MISSIONFORGE analysis engine and are gameplay estimates.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            data-testid="add-alternative"
            onClick={add}
            disabled={atLimit}
            className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-border px-4 text-sm font-medium enabled:hover:text-accent-cyan disabled:opacity-60"
          >
            <Copy aria-hidden className="h-4 w-4" />
            Duplicate baseline as alternative
          </button>
          <button
            type="button"
            data-testid="run-trade-study"
            onClick={execute}
            disabled={alternatives.length === 0 || run.kind === "running"}
            className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-accent-cyan/60 px-4 text-sm font-medium text-accent-cyan enabled:hover:bg-accent-cyan/10 disabled:opacity-60"
          >
            <Play aria-hidden className="h-4 w-4" />
            {run.kind === "running" ? "Comparing" : "Run trade study"}
          </button>
          <span className="text-xs text-muted">
            {alternatives.length} of {MAX_ALTERNATIVES} alternatives{atLimit ? ": up to 3 alternatives are allowed" : ""}
          </span>
        </div>
      </section>

      {alternatives.length === 0 ? (
        <p className="text-sm text-muted" data-testid="compare-empty">
          No alternatives yet. Duplicate the baseline, swap a component, then run the trade study.
        </p>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
          {alternatives.map((alt) => (
            <AlternativeCard
              key={alt.label}
              alternative={alt}
              baseline={mission}
              groups={catalog.groups}
              onChange={(category, id) => change(alt.label, category, id)}
              onRemove={() => remove(alt.label)}
            />
          ))}
        </div>
      )}

      <div aria-live="polite" className="space-y-3">
        {run.kind === "error" ? (
          <p
            role="alert"
            data-testid="compare-error"
            className="flex items-start gap-2 rounded-lg border border-accent-amber/60 p-3 text-sm"
          >
            <CircleAlert aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-accent-amber" />
            <span>{run.message} Your alternatives are kept; adjust them and run the study again.</span>
          </p>
        ) : null}
        {stale ? (
          <p data-testid="compare-stale" className="text-sm text-accent-amber">
            Out of date: the alternatives changed after this comparison. Run the trade study again.
          </p>
        ) : null}
        {run.kind === "done" ? <CompareTable result={run.result} labels={run.labels} /> : null}
      </div>
    </div>
  );
}

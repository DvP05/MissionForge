"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { StatusPill } from "@/components/common/StatusPill";
import { ErrorState, LoadingState } from "@/components/common/States";
import { apiGet, type DataOf } from "@/lib/api-client";
import { useMissionStore, type ScenarioId } from "@/state/mission-store";

type Templates = DataOf<Awaited<ReturnType<typeof apiGet<"/api/templates">>>>;
type Template = Templates[number];

/** Only NEO is playable until Task 7.1 ships the other scenarios. */
const ENABLED: ReadonlySet<ScenarioId> = new Set<ScenarioId>(["neo-rendezvous"]);

type Load =
  | { kind: "loading" }
  | { kind: "ready"; templates: Templates }
  | { kind: "error"; message: string };

export function ScenarioGrid() {
  const router = useRouter();
  const [load, setLoad] = useState<Load>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [startingId, setStartingId] = useState<ScenarioId | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const loadTemplate = useMissionStore((s) => s.loadTemplate);

  useEffect(() => {
    const controller = new AbortController();
    apiGet("/api/templates", { signal: controller.signal }).then((result) => {
      if (controller.signal.aborted) return;
      if (result.ok && result.data) setLoad({ kind: "ready", templates: result.data });
      else
        setLoad({
          kind: "error",
          message: result.error?.message ?? "Scenario templates could not be loaded.",
        });
    });
    return () => controller.abort();
  }, [attempt]);

  const retry = useCallback(() => {
    setLoad({ kind: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  const start = useCallback(
    async (template: Template) => {
      setStartError(null);
      setStartingId(template.scenarioId);
      const outcome = await loadTemplate(template.scenarioId);
      if (outcome.ok) {
        router.push(`/mission/${outcome.missionId}`);
        return;
      }
      setStartingId(null);
      setStartError(outcome.message);
    },
    [loadTemplate, router],
  );

  if (load.kind === "loading") return <LoadingState label="Loading scenarios" />;
  if (load.kind === "error")
    return <ErrorState title="Scenarios unavailable" message={load.message} onRetry={retry} />;

  return (
    <div className="space-y-4">
      {startError ? (
        <ErrorState title="Could not start the mission" message={startError} />
      ) : null}
      <ul className="grid gap-4 md:grid-cols-3">
        {load.templates.map((template) => {
          const enabled = ENABLED.has(template.scenarioId);
          const busy = startingId === template.scenarioId;
          return (
            <li
              key={template.scenarioId}
              data-testid={`scenario-card-${template.scenarioId}`}
              className="flex min-w-0 flex-col gap-3 rounded-xl border border-border bg-surface p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <h3 className="text-lg font-semibold">{template.title}</h3>
                {enabled ? null : <StatusPill tone="warn">Preview</StatusPill>}
              </div>
              <p className="text-sm text-muted">{template.narrative}</p>
              {template.topConstraints.length > 0 ? (
                <ul className="list-disc space-y-1 pl-5 text-xs text-muted">
                  {template.topConstraints.slice(0, 3).map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              ) : null}
              <div className="mt-auto pt-2">
                <button
                  type="button"
                  disabled={!enabled || startingId !== null}
                  aria-label={enabled ? undefined : `${template.title}: coming soon`}
                  onClick={() => start(template)}
                  className="min-h-11 w-full rounded-lg border border-accent-cyan/60 px-4 text-sm font-medium text-accent-cyan hover:bg-accent-cyan/10 disabled:cursor-not-allowed disabled:border-border disabled:text-muted disabled:hover:bg-transparent"
                >
                  {enabled ? (busy ? "Starting..." : "Start mission") : "Coming soon"}
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

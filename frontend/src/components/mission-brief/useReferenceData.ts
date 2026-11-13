"use client";

import { useCallback, useEffect, useState } from "react";

import type { InstrumentRef } from "@/components/science-traceability/build-trace-rows";
import { apiGet, type DataOf } from "@/lib/api-client";
import type { ScenarioId } from "@/state/mission-store";

type Templates = DataOf<Awaited<ReturnType<typeof apiGet<"/api/templates">>>>;
export type Template = Templates[number];

export type ReferenceData =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; template: Template; instruments: InstrumentRef[] };

/** Scenario template (narrative, constraints, optional objectives) + instrument catalogue. */
export function useReferenceData(scenarioId: ScenarioId): { data: ReferenceData; retry: () => void } {
  const [data, setData] = useState<ReferenceData>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    Promise.all([apiGet("/api/templates", { signal }), apiGet("/api/catalog", { signal })]).then(
      ([templates, catalog]) => {
        if (signal.aborted) return;
        const template = templates.ok ? templates.data?.find((t) => t.scenarioId === scenarioId) : undefined;
        const group = catalog.ok ? catalog.data?.groups.find((g) => g.category === "instrument") : undefined;
        if (!template || !group) {
          const error = (!templates.ok ? templates.error : catalog.error)?.message;
          setData({
            kind: "error",
            message: error ?? "The scenario brief or instrument catalogue could not be loaded.",
          });
          return;
        }
        setData({
          kind: "ready",
          template,
          instruments: group.components.map((c) => ({
            id: c.id,
            name: c.name,
            capabilities: c.capabilities ?? [],
          })),
        });
      },
    );
    return () => controller.abort();
  }, [scenarioId, attempt]);

  const retry = useCallback(() => {
    setData({ kind: "loading" });
    setAttempt((n) => n + 1);
  }, []);
  return { data, retry };
}

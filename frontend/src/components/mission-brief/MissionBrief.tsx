"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { FidelityBadge } from "@/components/common/FidelityBadge";
import { StatusPill } from "@/components/common/StatusPill";
import { ACTION_CLASS, ErrorState, LoadingState } from "@/components/common/States";
import { buildTraceRows } from "@/components/science-traceability/build-trace-rows";
import { TraceabilityTable, WeightsNote } from "@/components/science-traceability/TraceabilityTable";
import { useAnalysis } from "@/hooks/useAnalysis";
import { useMissionStore, type ScienceObjective } from "@/state/mission-store";
import { ConceptCard } from "./ConceptCard";
import { ObjectiveSelector, type ObjectiveChoice } from "./ObjectiveSelector";
import { useReferenceData } from "./useReferenceData";

/** Mission brief (M02a): scenario, top constraints, objective confirmation, traceability. */
export function MissionBrief() {
  const mission = useMissionStore((s) => s.mission);
  const analysis = useMissionStore((s) => s.analysis);
  const analysisRevision = useMissionStore((s) => s.analysisRevision);
  const status = useMissionStore((s) => s.status);
  const addObjective = useMissionStore((s) => s.addObjective);
  const removeObjective = useMissionStore((s) => s.removeObjective);
  const updateObjective = useMissionStore((s) => s.updateObjective);
  const commitRevision = useMissionStore((s) => s.commitRevision);
  const { retry: retryAnalysis } = useAnalysis();
  const { data, retry } = useReferenceData(mission?.scenarioId ?? "neo-rendezvous");

  const template = data.kind === "ready" ? data.template : null;
  const instruments = data.kind === "ready" ? data.instruments : null;

  const choices = useMemo<ObjectiveChoice[]>(() => {
    if (!mission || !template) return [];
    const current = new Map(mission.scienceObjectives.map((o) => [o.id, o]));
    const candidates = [...template.missionState.scienceObjectives, ...(template.optionalObjectives ?? [])];
    const known = new Set(candidates.map((o) => o.id));
    const extras = mission.scienceObjectives.filter((o) => !known.has(o.id));
    return [...candidates, ...extras].map((o) => ({
      objective: current.get(o.id) ?? o,
      selected: current.has(o.id),
    }));
  }, [mission, template]);

  const rows = useMemo(() => {
    if (!mission || !instruments) return [];
    const selected = instruments.filter((i) => mission.architecture.instrumentIds.includes(i.id));
    // Only an analysis for the current revision may drive row status.
    const current =
      analysis && analysisRevision === mission.designRevision && analysis.missionId === mission.missionId
        ? analysis
        : null;
    return buildTraceRows(mission.scienceObjectives, selected, current);
  }, [mission, instruments, analysis, analysisRevision]);

  if (!mission) return null;
  if (data.kind === "loading") return <LoadingState label="Loading mission brief" />;
  if (data.kind === "error") {
    return <ErrorState title="Mission brief unavailable" message={data.message} onRetry={retry} />;
  }

  const onToggle = (objective: ScienceObjective, selected: boolean) => {
    if (selected) addObjective(objective);
    else removeObjective(objective.id);
    commitRevision();
  };
  const onPriority = (objectiveId: string, priority: number) => {
    updateObjective(objectiveId, { priority });
    commitRevision();
  };

  const currentAnalysis = analysis && analysisRevision === mission.designRevision ? analysis : null;

  return (
    <div className="space-y-8">
      <ConceptCard />

      <section aria-labelledby="scenario-heading" className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <h2 id="scenario-heading" className="text-lg font-semibold">
            Scenario
          </h2>
          <span data-testid="starter-design-label">
            <StatusPill tone="info">Starter design</StatusPill>
          </span>
        </div>
        <p data-testid="brief-narrative" className="text-base">
          {data.template.narrative}
        </p>
        <p className="text-sm text-muted">
          The starter design is a working spacecraft with one deliberate weakness for you to find and fix.
        </p>
        <div>
          <h3 className="mb-1 text-sm font-semibold">Top constraints</h3>
          <ul data-testid="brief-constraints" className="list-disc space-y-1 pl-5 text-sm text-muted">
            {data.template.topConstraints.slice(0, 3).map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
      </section>

      <ObjectiveSelector choices={choices} onToggle={onToggle} onPriority={onPriority} />

      <section aria-labelledby="trace-heading" className="space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="trace-heading" className="text-lg font-semibold">
            Science traceability
          </h2>
          <p data-testid="science-coverage" className="flex flex-wrap items-center gap-2 text-sm">
            {currentAnalysis ? (
              <>
                <span>Science coverage {Math.round(currentAnalysis.science.coverageScore)}%</span>
                <FidelityBadge fidelity="derived" />
              </>
            ) : status === "error" ? null : (
              <span className="text-muted">Analysing with the backend</span>
            )}
          </p>
        </div>
        {status === "error" ? (
          <div
            data-testid="analysis-error"
            role="alert"
            className="flex flex-wrap items-center gap-3 rounded-lg border border-accent-amber/60 p-3 text-sm"
          >
            <span>The backend analysis could not be completed. Rows show capability matches only.</span>
            <button type="button" onClick={retryAnalysis} className={ACTION_CLASS}>
              Retry
            </button>
          </div>
        ) : null}
        <TraceabilityTable rows={rows} hasAnalysis={currentAnalysis !== null} />
        <WeightsNote />
      </section>

      <div>
        <Link href={`/architect/${mission.missionId}`} className={`${ACTION_CLASS} gap-2`}>
          Continue to Architect
          <ArrowRight aria-hidden className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}

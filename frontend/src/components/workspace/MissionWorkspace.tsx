"use client";

import { useEffect, useSyncExternalStore, type ReactNode } from "react";

import { ExportButton, ImportButton } from "@/components/persistence/PackageControls";
import { RunsPanel } from "@/components/persistence/RunsPanel";
import { StatusPill } from "@/components/common/StatusPill";
import { LoadingState, NotFoundState } from "@/components/common/States";
import { selectSaveState } from "@/state/selectors";
import { MissionHelp } from "@/components/progress/MissionHelp";
import { MissionProgress } from "@/components/progress/MissionProgress";
import { MissionStageNav } from "@/components/progress/MissionStageNav";
import { ReadinessSummary } from "@/components/progress/ReadinessSummary";
import { useMissionProgress } from "@/components/progress/useMissionProgress";
import { writeActiveMission } from "@/lib/persistence/active-mission";
import { useMissionStore } from "@/state/mission-store";

export type WorkspaceView = "brief" | "science" | "architect" | "arena" | "readiness";




const NOT_FOUND_COPY: Record<string, string> = {
  corrupt: "The saved mission could not be read. It may be damaged; start a new mission.",
  unavailable: "Browser storage is unavailable, so this mission cannot be restored.",
  "not-found": "This mission is not saved in this browser.",
};

/**
 * Route guard + chrome for mission-scoped pages. Restores the mission from
 * browser storage by ID; renders loading / not-found states otherwise.
 */
export function MissionWorkspace({
  missionId,
  view,
  children,
}: {
  missionId: string;
  view: WorkspaceView;
  children: ReactNode;
}) {
  const hydrate = useMissionStore((s) => s.hydrate);
  const mission = useMissionStore((s) => s.mission);
  const designRevision = useMissionStore((s) => s.designRevision);
  const saveState = useMissionStore(selectSaveState);
  // Storage only exists in the browser; render a stable loading state during SSR/hydration.
  const mounted = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
  const hydration = useMissionStore((s) => s.hydration);
  const progress = useMissionProgress(missionId);
  const openMissionId = mission?.missionId ?? null;

  // the station rail follows the mission the player is working on
  useEffect(() => {
    if (openMissionId === missionId) writeActiveMission(missionId);
  }, [openMissionId, missionId]);

  // Edits not yet committed as a revision would be lost on leaving: ask first.
  useEffect(() => {
    if (saveState !== "unsaved") return;
    const guard = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, [saveState]);

  useEffect(() => {
    hydrate(missionId);
  }, [hydrate, missionId]);

  const settled = mounted && hydration?.missionId === missionId;
  if (!settled) return <LoadingState label="Loading mission" />;
  if (!hydration.ok || !mission || mission.missionId !== missionId) {
    const reason = hydration.ok ? "not-found" : hydration.reason;
    return <NotFoundState message={NOT_FOUND_COPY[reason]} />;
  }

  return (
    <div className="space-y-5">
      <header className="space-y-3">
        <div className="panel relative overflow-hidden p-4 sm:p-5">
          <div aria-hidden className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 bg-[url('/backdrops/star-chart.svg')] bg-contain bg-no-repeat opacity-70" />
          <div className="relative flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <StatusPill tone="info">{mission.scenarioId}</StatusPill>
                <span className="text-xs text-muted">Target: {mission.destination.name}</span>
              </div>
              <h1 data-testid="workspace-title" className="break-words text-3xl font-semibold tracking-tight sm:text-4xl">
                {mission.title}
              </h1>
              <p data-testid="workspace-mission-id" className="break-all font-mono text-xs text-muted">
                {mission.missionId}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <StatusPill testId="revision-pill">Revision {designRevision}</StatusPill>
              <span data-testid="save-status">
                {saveState === "saved" ? (
                  <StatusPill tone="ok">Saved in this browser</StatusPill>
                ) : saveState === "unsaved" ? (
                  <StatusPill tone="warn">Unsaved edits</StatusPill>
                ) : (
                  <StatusPill tone="warn">Not saved: browser storage unavailable</StatusPill>
                )}
              </span>
              <ReadinessSummary />
              <MissionHelp />
            </div>
          </div>
        </div>
        {saveState === "not-saved" ? (
          <div data-testid="storage-export-prompt" role="alert" className="flex max-w-2xl flex-wrap items-center gap-3 rounded-lg border border-accent-amber/60 p-3 text-sm">
            <p>
              Your browser could not save this mission (storage is full or blocked). You can keep working, but changes
              will be lost on reload. Export a package to keep your design.
            </p>
            <ExportButton testId="storage-export-button" label="Export package now" />
          </div>
        ) : null}
        <div className="flex flex-wrap items-center justify-between gap-3">
          {progress ? (
            <MissionStageNav missionId={missionId} view={view} stages={progress.stages} latestRunId={progress.runIds.at(-1) ?? null} />
          ) : (
            <span />
          )}
          <div className="flex flex-wrap items-start gap-2" data-testid="package-controls">
            <ExportButton />
            <ImportButton />
          </div>
        </div>
        <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          {progress ? <MissionProgress progress={progress} /> : <span />}
          <RunsPanel missionId={missionId} />
        </div>
      </header>
      <div>{children}</div>
    </div>
  );
}

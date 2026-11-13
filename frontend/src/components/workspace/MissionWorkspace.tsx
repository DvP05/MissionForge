"use client";

import Link from "next/link";
import { useEffect, useSyncExternalStore, type ReactNode } from "react";

import { StatusPill } from "@/components/common/StatusPill";
import { LoadingState, NotFoundState } from "@/components/common/States";
import { selectSaveState } from "@/state/selectors";
import { useMissionStore } from "@/state/mission-store";

export type WorkspaceView = "brief" | "architect" | "arena";

const TABS: { view: WorkspaceView; label: string; base: string }[] = [
  { view: "brief", label: "Brief", base: "/mission" },
  { view: "architect", label: "Architect", base: "/architect" },
  { view: "arena", label: "Arena", base: "/arena" },
];

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
    <div className="space-y-6">
      <header className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill tone="info">{mission.scenarioId}</StatusPill>
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
        </div>
        <h1 data-testid="workspace-title" className="break-words text-3xl font-semibold tracking-tight">
          {mission.title}
        </h1>
        <p data-testid="workspace-mission-id" className="break-all font-mono text-xs text-muted">
          {mission.missionId}
        </p>
        <nav aria-label="Mission workspace" className="flex flex-wrap gap-2">
          {TABS.map((tab) => (
            <Link
              key={tab.view}
              href={`${tab.base}/${missionId}`}
              aria-current={tab.view === view ? "page" : undefined}
              className={`inline-flex min-h-11 items-center rounded-lg border px-4 text-sm font-medium ${
                tab.view === view
                  ? "border-accent-cyan/60 bg-accent-cyan/10 text-accent-cyan"
                  : "border-border text-muted hover:text-foreground"
              }`}
            >
              {tab.label}
            </Link>
          ))}
        </nav>
      </header>
      <div>{children}</div>
    </div>
  );
}

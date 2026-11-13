"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useSyncExternalStore, type ReactNode } from "react";

import { StatusPill } from "@/components/common/StatusPill";
import { LoadingState, NotFoundState } from "@/components/common/States";
import { selectSaveState } from "@/state/selectors";
import { isValidMissionId, loadMission } from "@/lib/persistence/storage";
import { useMissionStore } from "@/state/mission-store";

export type WorkspaceView = "brief" | "architect" | "arena";

const TABS: { view: WorkspaceView; label: string; base: string }[] = [
  { view: "brief", label: "Brief", base: "/mission" },
  { view: "architect", label: "Architect", base: "/architect" },
  { view: "arena", label: "Arena", base: "/arena" },
];

type Probe = { ok: true } | { ok: false; reason: "not-found" | "corrupt" | "unavailable" };

/** Read-only check of browser storage (no store mutation) used to pick the view state. */
function hydrateProbe(missionId: string): Probe {
  if (!isValidMissionId(missionId)) return { ok: false, reason: "not-found" };
  const loaded = loadMission(missionId);
  if (loaded.ok) return { ok: true };
  const code = loaded.error.code;
  return { ok: false, reason: code === "quota" ? "unavailable" : code };
}

const NOT_FOUND_COPY: Record<string, string> = {
  corrupt: "The saved mission could not be read. It may be damaged; start a new mission.",
  unavailable: "Browser storage is unavailable, so this mission cannot be restored.",
  "not-found": "This mission is not saved in this browser.",
};

/**
 * Route guard + chrome for mission-scoped pages. Restores the mission from
 * browser storage by ID; renders loading / not-found states otherwise.
 */
function WorkspaceInner({
  view,
  children,
}: {
  view: WorkspaceView;
  children: ReactNode;
}) {
  const params = useParams<{ missionId: string }>();
  const missionId = params.missionId;
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
  const inStore = mission !== null && mission.missionId === missionId;
  const probe = useMemo(
    () => (mounted && !inStore ? hydrateProbe(missionId) : null),
    [mounted, inStore, missionId],
  );

  useEffect(() => {
    if (probe?.ok) hydrate(missionId);
  }, [probe, hydrate, missionId]);

  if (!mounted || (!inStore && (probe === null || probe.ok))) {
    return <LoadingState label="Loading mission" />;
  }
  if (!inStore || !mission) {
    const reason = probe && !probe.ok ? probe.reason : "not-found";
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

/** Suspense boundary is required: the route param is only known at request time. */
export function MissionWorkspace(props: { view: WorkspaceView; children: ReactNode }) {
  return (
    <Suspense fallback={<LoadingState label="Loading mission" />}>
      <WorkspaceInner {...props} />
    </Suspense>
  );
}

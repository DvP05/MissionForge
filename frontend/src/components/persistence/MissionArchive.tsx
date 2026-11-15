"use client";

import Link from "next/link";

import { StatusPill } from "@/components/common/StatusPill";
import { LoadingState } from "@/components/common/States";
import { ImportButton } from "./PackageControls";
import { useSavedMissions } from "./SavedMissions";

const LINK =
  "inline-flex min-h-9 items-center rounded-md border border-border px-3 text-sm text-muted hover:border-accent-cyan/50 hover:text-foreground";

/** Mission Archive: saved designs, their revisions and every cached run with its report. */
export function MissionArchive() {
  const load = useSavedMissions();
  if (load.kind === "loading") return <LoadingState label="Reading saved missions" />;
  if (load.kind === "unavailable") {
    return <p className="text-sm text-accent-amber">Browser storage is unavailable: {load.message}</p>;
  }
  return (
    <div className="space-y-6" data-testid="mission-archive">
      {load.entries.length === 0 ? (
        <p data-testid="archive-empty" className="panel p-5 text-sm text-muted">
          No saved missions yet. Start one from the <Link href="/" className="text-accent-cyan underline">hangar</Link>.
        </p>
      ) : (
        <ul className="space-y-4">
          {load.entries.map(({ mission, runs }) => (
            <li key={mission.missionId} data-testid={`archive-mission-${mission.missionId}`} className="panel space-y-3 p-5">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-semibold">{mission.title}</h2>
                <StatusPill tone="info">{mission.scenarioId}</StatusPill>
                <StatusPill>Revision {mission.designRevision}</StatusPill>
              </div>
              <p className="break-all font-mono text-xs text-muted">{mission.missionId}</p>
              <div className="flex flex-wrap gap-2">
                <Link href={`/mission/${mission.missionId}`} className={LINK}>Brief</Link>
                <Link href={`/science/${mission.missionId}`} className={LINK}>Science lab</Link>
                <Link href={`/architect/${mission.missionId}`} className={LINK}>Architect</Link>
                <Link href={`/arena/${mission.missionId}`} className={LINK}>Trade study</Link>
              </div>
              {runs.length > 0 ? (
                <div className="space-y-2">
                  <h3 className="text-sm font-medium text-muted">Flown missions ({runs.length})</h3>
                  <ul className="divide-y divide-border/60 rounded-lg border border-border">
                    {runs.map(({ run }) => (
                      <li key={run.runId} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm">
                        <span className="min-w-0 break-all font-mono text-xs">
                          {run.runId} · seed {run.seed} · design revision {run.designRevision}
                        </span>
                        <span className="flex gap-2">
                          <Link href={`/control/${run.runId}`} className={LINK}>Replay</Link>
                          <Link href={`/review/${run.runId}`} className={LINK}>Report</Link>
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="text-xs text-muted">Not flown yet.</p>
              )}
            </li>
          ))}
        </ul>
      )}
      <section aria-labelledby="archive-import" className="space-y-2">
        <h2 id="archive-import" className="text-lg font-semibold">Restore from a package</h2>
        <ImportButton />
      </section>
    </div>
  );
}

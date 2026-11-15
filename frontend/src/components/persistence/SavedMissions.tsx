"use client";

import { ArrowRight, Rocket } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { STORAGE_CHANGED_EVENT } from "@/lib/persistence/events";
import { listCachedRuns, type RunData } from "@/lib/persistence/run-cache";
import { listMissions, type MissionSummary } from "@/lib/persistence/storage";

export interface SavedEntry {
  mission: MissionSummary;
  runs: RunData[];
}

type Load = { kind: "loading" } | { kind: "unavailable"; message: string } | { kind: "ready"; entries: SavedEntry[] };

/** Saved missions and their cached runs, re-read whenever browser storage changes. */
export function useSavedMissions(): Load {
  const [load, setLoad] = useState<Load>({ kind: "loading" });
  useEffect(() => {
    const read = () => {
      const res = listMissions();
      if (!res.ok) {
        setLoad({ kind: "unavailable", message: res.error.message });
        return;
      }
      setLoad({
        kind: "ready",
        entries: res.value.map((mission) => ({ mission, runs: listCachedRuns(mission.missionId) })),
      });
    };
    read();
    window.addEventListener(STORAGE_CHANGED_EVENT, read);
    window.addEventListener("storage", read);
    return () => {
      window.removeEventListener(STORAGE_CHANGED_EVENT, read);
      window.removeEventListener("storage", read);
    };
  }, []);
  return load;
}

/** Hangar "continue" list: the player's saved architectures in this browser. */
export function SavedMissions({ limit }: { limit?: number }) {
  const load = useSavedMissions();
  if (load.kind === "loading") return null;
  if (load.kind === "unavailable") {
    return <p className="text-sm text-muted">Saved missions are unavailable: {load.message}</p>;
  }
  if (load.entries.length === 0) {
    return (
      <p data-testid="saved-missions-empty" className="text-sm text-muted">
        No saved missions in this browser yet. Start a scenario below; every design revision is saved here
        automatically.
      </p>
    );
  }
  const entries = limit ? load.entries.slice(0, limit) : load.entries;
  return (
    <ul data-testid="saved-missions" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {entries.map(({ mission, runs }) => (
        <li key={mission.missionId} className="panel flex min-w-0 flex-col gap-2 p-4">
          <div className="flex min-w-0 items-start gap-3">
            <Rocket aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-accent-cyan" />
            <div className="min-w-0">
              <p className="truncate font-medium">{mission.title}</p>
              <p className="truncate font-mono text-xs text-muted">
                {mission.scenarioId} · revision {mission.designRevision} · {runs.length} run{runs.length === 1 ? "" : "s"}
              </p>
            </div>
          </div>
          <div className="mt-auto flex flex-wrap gap-2 pt-1 text-sm">
            <Link
              href={`/architect/${mission.missionId}`}
              className="inline-flex min-h-9 items-center gap-1 rounded-md border border-accent-cyan/50 bg-accent-cyan/10 px-3 text-accent-cyan hover:bg-accent-cyan/20"
            >
              Continue design <ArrowRight aria-hidden className="h-3.5 w-3.5" />
            </Link>
            <Link
              href={`/mission/${mission.missionId}`}
              className="inline-flex min-h-9 items-center rounded-md border border-border px-3 text-muted hover:text-foreground"
            >
              Brief
            </Link>
          </div>
        </li>
      ))}
    </ul>
  );
}

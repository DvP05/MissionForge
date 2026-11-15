"use client";

import { useEffect, useMemo, useState } from "react";

import { STORAGE_CHANGED_EVENT } from "@/lib/persistence/events";
import { listCachedRuns } from "@/lib/persistence/run-cache";
import { loadMission } from "@/lib/persistence/storage";
import {
  challenges,
  computeStages,
  earnedBadges,
  PROGRESS_EVENT,
  readProgress,
  recordBadges,
  type ProgressRecord,
} from "@/lib/progress/progress";
import { useMissionStore, type MissionState } from "@/state/mission-store";

interface Snapshot {
  savedMission: MissionState | null;
  runIds: string[];
  record: ProgressRecord;
}

function read(missionId: string): Snapshot {
  const loaded = loadMission(missionId);
  return {
    savedMission: loaded.ok ? loaded.value : null,
    runIds: listCachedRuns(missionId)
      .sort((a, b) => a.run.designRevision - b.run.designRevision)
      .map((r) => r.run.runId),
    record: readProgress(missionId),
  };
}

/**
 * Progress for a mission from real state: the open mission (or the saved copy), the backend
 * analysis of the current revision only, cached runs and recorded player actions. Earned badges
 * are persisted; those earned at the current revision are returned in `fresh` for a one-time
 * milestone acknowledgement.
 */
export function useMissionProgress(missionId: string) {
  const live = useMissionStore((s) => (s.mission?.missionId === missionId ? s.mission : null));
  const analysis = useMissionStore((s) =>
    s.mission?.missionId === missionId && s.analysis && s.analysisRevision === s.designRevision ? s.analysis : null,
  );
  const previous = useMissionStore((s) => (s.mission?.missionId === missionId ? s.previousAnalysis : null));
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [dismissed, setDismissed] = useState<string[]>([]);

  useEffect(() => {
    const update = () => setSnap(read(missionId));
    update();
    window.addEventListener(STORAGE_CHANGED_EVENT, update);
    window.addEventListener(PROGRESS_EVENT, update);
    window.addEventListener("storage", update);
    return () => {
      window.removeEventListener(STORAGE_CHANGED_EVENT, update);
      window.removeEventListener(PROGRESS_EVENT, update);
      window.removeEventListener("storage", update);
    };
  }, [missionId, live?.designRevision]);

  const mission = live ?? snap?.savedMission ?? null;
  const record = useMemo(() => snap?.record ?? { flags: {}, badges: {} }, [snap]);

  // persist badges the current engine result earns (once each)
  useEffect(() => {
    if (!mission || !analysis) return;
    const ids = earnedBadges(analysis, previous, record);
    // persisted once each; the progress event then refreshes `record`
    // a starter design earns nothing by itself: engine-result badges need a player change
    recordBadges(missionId, mission.designRevision === 0 ? ids.filter((b) => b === "risk-reviewed") : ids, mission.designRevision);
  }, [analysis, previous, record, mission, missionId]);

  if (!mission || !snap) return null;
  const stages = computeStages({ mission, analysis, runIds: snap.runIds, record });
  // a badge earned at this revision is acknowledged once, until dismissed
  const fresh = Object.entries(record.badges)
    .filter(([id, rev]) => rev === mission.designRevision && !dismissed.includes(id))
    .map(([id]) => id);
  return {
    mission,
    stages,
    next: stages.find((s) => s.status !== "complete") ?? null,
    badges: Object.keys(record.badges),
    fresh,
    clearFresh: () => setDismissed((d) => [...d, ...fresh]),
    challenges: challenges(analysis),
    runIds: snap.runIds,
    analysisCurrent: analysis !== null,
  };
}

"use client";

import { MissionStageNav, type StageView } from "./MissionStageNav";
import { useMissionProgress } from "./useMissionProgress";

/**
 * Stage rail on run pages (mission control, review), so flying and debriefing stay inside the
 * same mission journey. Absent when the run's mission is not saved in this browser (e.g. an
 * imported run whose design was not kept).
 */
export function RunStageBar({ missionId, view }: { missionId: string; view: Extract<StageView, "control" | "review"> }) {
  const progress = useMissionProgress(missionId);
  if (!progress) return null;
  return <MissionStageNav missionId={missionId} view={view} stages={progress.stages} latestRunId={progress.runIds.at(-1) ?? null} />;
}

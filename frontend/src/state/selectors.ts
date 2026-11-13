import type { components } from "@/lib/api/schema";
import type { MissionStoreState } from "@/state/mission-store";

type ConstraintStatus = components["schemas"]["ConstraintResult"]["status"];

export const selectMission = (s: MissionStoreState) => s.mission;

/** True when the shown analysis does not belong to the current design revision. */
export const selectIsAnalysisStale = (s: MissionStoreState): boolean =>
  s.analysis !== null && s.analysisRevision !== s.designRevision;

export const selectHasUncommittedEdits = (s: MissionStoreState): boolean => s.dirty;

export type SaveState = "saved" | "unsaved" | "not-saved";

/** Presentation state for the saved/dirty indicator. */
export const selectSaveState = (s: MissionStoreState): SaveState =>
  s.saveError ? "not-saved" : s.dirty ? "unsaved" : "saved";

/** Tallies backend-reported constraint statuses (a count, not a calculation). */
export function countConstraintStatuses(
  analysis: MissionStoreState["analysis"],
): Record<ConstraintStatus, number> {
  const counts: Record<ConstraintStatus, number> = {
    pass: 0,
    warning: 0,
    fail: 0,
    "not-modelled": 0,
  };
  for (const c of analysis?.constraints ?? []) counts[c.status] += 1;
  return counts;
}

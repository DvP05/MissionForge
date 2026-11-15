/**
 * The one path for add / replace / remove (design_update.md 6.3). Every confirmed change goes
 * through the mission store's canonical actions (selectComponent + commitRevision), records
 * what it replaced for a safe undo, and asks the viewport to play the attach animation.
 * Nothing here computes an engineering value.
 */
import { useArchitectUi } from "@/state/architect-ui-store";
import { useChangeStore, type ChangeKind } from "@/state/change-store";
import { useMissionStore, type ComponentCategory, type MissionState, type ScienceObjective } from "@/state/mission-store";
import { conflictsForCandidate, selectedIds, type CatalogComponent } from "./catalog-helpers";

/** What clicking a card's primary action means for this component right now. */
export function actionFor(mission: MissionState, category: ComponentCategory, componentId: string): ChangeKind | "installed" {
  const chosen = selectedIds(mission, category);
  if (category === "instrument") return chosen.includes(componentId) ? "remove" : "add";
  return chosen.includes(componentId) ? "installed" : "replace";
}

/**
 * Whether a change can be applied without asking: only an add with no catalogue conflict.
 * Replacements and removals always show old/new or what is lost first.
 */
export function needsConfirmation(
  index: Map<string, CatalogComponent>,
  mission: MissionState,
  kind: ChangeKind,
  category: ComponentCategory,
  componentId: string,
): boolean {
  if (kind !== "add") return true;
  return conflictsForCandidate(index, mission, category, componentId).length > 0;
}

/** Apply a change to the canonical design (one revision) and remember it for undo. */
export function applyChange(kind: ChangeKind, category: ComponentCategory, componentId: string): void {
  const store = useMissionStore.getState();
  const mission = store.mission;
  if (!mission) return;
  const before = mission.architecture;
  const replacedId = kind === "replace" ? (selectedIds(mission, category)[0] ?? null) : null;
  store.selectComponent(category, componentId);
  store.commitRevision();
  const revision = useMissionStore.getState().designRevision;
  useChangeStore.getState().recordApplied({ kind, category, componentId, replacedId, revision, before });
  const ui = useArchitectUi.getState();
  if (kind === "remove") ui.select(null, category);
  else ui.markInstalled(componentId);
}

/** Entry point for every add / replace / remove button. */
export function requestChange(
  index: Map<string, CatalogComponent>,
  category: ComponentCategory,
  componentId: string,
  opener: HTMLElement | null,
): void {
  const mission = useMissionStore.getState().mission;
  if (!mission) return;
  const kind = actionFor(mission, category, componentId);
  if (kind === "installed") return;
  if (needsConfirmation(index, mission, kind, category, componentId)) {
    useChangeStore.getState().request({ kind, category, componentId, opener });
  } else {
    applyChange(kind, category, componentId);
  }
}

/** Undo the last change by restoring the design before it, as a new revision. */
export function undoLastChange(): void {
  const applied = useChangeStore.getState().applied;
  const store = useMissionStore.getState();
  if (!applied || store.designRevision !== applied.revision) return;
  store.restoreArchitecture(applied.before);
  useChangeStore.getState().clearApplied();
}

/**
 * Required measurements that would be left with no installed instrument of the needed
 * capability if `componentId` were removed (catalogue capability mapping only; the
 * backend analysis re-checks coverage after the change).
 */
export function measurementsLost(
  mission: MissionState,
  index: Map<string, CatalogComponent>,
  componentId: string,
): { objective: ScienceObjective; measurement: ScienceObjective["requiredMeasurements"][number] }[] {
  const remaining = mission.architecture.instrumentIds.filter((id) => id !== componentId).map((id) => index.get(id));
  const capable = (cap: string) => remaining.some((c) => (c?.capabilities ?? []).includes(cap));
  const removed = index.get(componentId);
  const out: ReturnType<typeof measurementsLost> = [];
  for (const objective of mission.scienceObjectives) {
    for (const measurement of objective.requiredMeasurements) {
      const cap = measurement.instrumentCapability;
      if ((removed?.capabilities ?? []).includes(cap) && !capable(cap)) out.push({ objective, measurement });
    }
  }
  return out;
}

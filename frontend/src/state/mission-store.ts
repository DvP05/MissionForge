import { create } from "zustand";

import { apiGet } from "@/lib/api-client";
import type { components } from "@/lib/api/schema";
import {
  isValidMissionId,
  loadMission,
  saveMission,
  type StorageError,
} from "@/lib/persistence/storage";

/**
 * UI-only mission workspace state. The store edits MissionState fields and bumps
 * designRevision on commit; it never calculates engineering results. Analysis
 * numbers come exclusively from backend `MissionAnalysis` responses.
 */
type Schemas = components["schemas"];
export type MissionState = Schemas["MissionState"];
export type MissionAnalysis = Schemas["MissionAnalysis"];
export type ScienceObjective = Schemas["ScienceObjective"];
export type OperationsPlan = Schemas["OperationsPlan"];
export type MissionConstraints = Schemas["MissionConstraints"];
export type ScenarioId = MissionState["scenarioId"];

/** Objective count bounds from F-002 (R25). */
export const MIN_OBJECTIVES = 2;
export const MAX_OBJECTIVES = 4;

export type AnalysisStatus = "idle" | "calculating" | "stale" | "error";

/** Catalogue categories (API `category`) that map onto architecture fields. */
export type ComponentCategory = Schemas["CatalogComponent"]["category"];

const SINGLE_SELECT_FIELD = {
  launch: "launchVehicleId",
  bus: "busId",
  propulsion: "propulsionId",
  power: "powerId",
  adcs: "adcsId",
  communications: "communicationsId",
  thermal: "thermalId",
  cdh: "cdhId",
  ground: "groundSegmentId",
} as const;

export type LoadOutcome =
  | { ok: true; missionId: string; saved: boolean }
  | { ok: false; code: string; message: string; retryable: boolean };

/** One committed design change, kept for this session only (drawer "recent changes"). */
export interface ChangeLogEntry {
  revision: number;
  category: ComponentCategory;
  /** Previous selection (null when an instrument was added). */
  fromId: string | null;
  /** New selection (null when an instrument was removed). */
  toId: string | null;
}

const CHANGE_LOG_LIMIT = 20;

export type HydrateOutcome =
  | { ok: true }
  | { ok: false; reason: "not-found" | "corrupt" | "unavailable"; message: string };

export type HydrationRecord = { missionId: string } & HydrateOutcome;

export interface MissionStoreState {
  /** Result of the latest hydrate() call, for route guards to render from. */
  hydration: HydrationRecord | null;
  mission: MissionState | null;
  designRevision: number;
  analysis: MissionAnalysis | null;
  analysisRevision: number | null;
  status: AnalysisStatus;
  /** True while edits exist that have not been committed as a new revision. */
  dirty: boolean;
  /** Last persistence failure, if any (UI keeps working in memory). */
  saveError: StorageError | null;
  /** Component changes made since the last commit (becomes changeLog entries on commit). */
  pendingChanges: Omit<ChangeLogEntry, "revision">[];
  /** Committed component changes this session, newest first. */
  changeLog: ChangeLogEntry[];

  loadTemplate: (scenarioId: ScenarioId, seed?: number) => Promise<LoadOutcome>;
  hydrate: (missionId: string) => HydrateOutcome;
  selectComponent: (category: ComponentCategory, componentId: string) => void;
  updateObjective: (objectiveId: string, patch: Partial<Omit<ScienceObjective, "id">>) => void;
  /** Adds an objective (e.g. an optional one from the scenario template); no-op if the id exists. */
  addObjective: (objective: ScienceObjective) => void;
  /** Removes an objective (and its observation-plan items); never goes below MIN_OBJECTIVES (R25). */
  removeObjective: (objectiveId: string) => void;
  updateOperations: (patch: Partial<OperationsPlan>) => void;
  updateConstraints: (patch: Partial<MissionConstraints>) => void;
  /** Phase 5: use a served JPL option as the trajectory + destination (new revision). */
  setTrajectory: (trajectory: MissionState["trajectory"], destination: MissionState["destination"]) => void;
  commitRevision: () => void;
  setCalculating: () => void;
  /** Applies a backend analysis only if it matches the current design revision. */
  applyAnalysis: (analysis: MissionAnalysis) => boolean;
  setAnalysisError: () => void;
  reset: () => void;
}

/**
 * Mission-scoped state reset by loadTemplate/hydrate/reset. `hydration` is
 * deliberately NOT here: a mounted workspace renders from it, so resetting it
 * would strand the guard on "loading" (no effect re-runs to restore it).
 */
const EMPTY = {
  mission: null,
  designRevision: 0,
  analysis: null,
  analysisRevision: null,
  status: "idle" as AnalysisStatus,
  dirty: false,
  saveError: null,
  pendingChanges: [] as Omit<ChangeLogEntry, "revision">[],
  changeLog: [] as ChangeLogEntry[],
};

export const useMissionStore = create<MissionStoreState>()((set, get) => {
  const edit = (change: (m: MissionState) => MissionState) => {
    const { mission } = get();
    if (!mission) return;
    const next = change(mission);
    if (next === mission) return;
    set({ mission: next, dirty: true });
  };

  return {
    ...EMPTY,
    hydration: null,

    async loadTemplate(scenarioId, seed) {
      const result = await apiGet("/api/templates/{scenario_id}/default-mission", {
        pathParams: { scenario_id: scenarioId },
        query: seed === undefined ? undefined : { seed },
      });
      if (!result.ok || !result.data) {
        return {
          ok: false,
          code: result.error?.code ?? "UNKNOWN",
          message: result.error?.message ?? "The mission template could not be loaded.",
          retryable: result.error?.retryable ?? true,
        };
      }
      const mission = result.data;
      const saved = saveMission(mission);
      set({
        ...EMPTY,
        mission,
        designRevision: mission.designRevision,
        saveError: saved.ok ? null : saved.error,
      });
      return { ok: true, missionId: mission.missionId, saved: saved.ok };
    },

    hydrate(missionId) {
      const finish = (outcome: HydrateOutcome): HydrateOutcome => {
        set({ hydration: { missionId, ...outcome } });
        return outcome;
      };
      const current = get().mission;
      if (current && current.missionId === missionId) return finish({ ok: true });
      if (!isValidMissionId(missionId)) {
        return finish({ ok: false, reason: "not-found", message: "Mission id is not valid." });
      }
      const loaded = loadMission(missionId);
      if (!loaded.ok) {
        const reason = loaded.error.code === "quota" ? "unavailable" : loaded.error.code;
        return finish({ ok: false, reason, message: loaded.error.message });
      }
      set({
        ...EMPTY,
        mission: loaded.value,
        designRevision: loaded.value.designRevision,
      });
      return finish({ ok: true });
    },

    selectComponent(category, componentId) {
      const mission = get().mission;
      if (!mission) return;
      let change: Omit<ChangeLogEntry, "revision">;
      if (category === "instrument") {
        const has = mission.architecture.instrumentIds.includes(componentId);
        change = {
          category,
          fromId: has ? componentId : null,
          toId: has ? null : componentId,
        };
        edit((m) => {
          const ids = m.architecture.instrumentIds;
          const next = ids.includes(componentId)
            ? ids.filter((id) => id !== componentId)
            : [...ids, componentId];
          return { ...m, architecture: { ...m.architecture, instrumentIds: next } };
        });
      } else {
        const field = SINGLE_SELECT_FIELD[category];
        const fromId = mission.architecture[field];
        if (fromId === componentId) return;
        change = { category, fromId, toId: componentId };
        edit((m) => ({ ...m, architecture: { ...m.architecture, [field]: componentId } }));
      }
      set((s) => ({ pendingChanges: [...s.pendingChanges, change] }));
    },

    updateObjective(objectiveId, patch) {
      edit((m) => ({
        ...m,
        scienceObjectives: m.scienceObjectives.map((o) =>
          o.id === objectiveId ? { ...o, ...patch } : o,
        ),
      }));
    },

    addObjective(objective) {
      edit((m) =>
        m.scienceObjectives.some((o) => o.id === objective.id)
          ? m
          : { ...m, scienceObjectives: [...m.scienceObjectives, objective] },
      );
    },

    removeObjective(objectiveId) {
      edit((m) => {
        const removed = m.scienceObjectives.find((o) => o.id === objectiveId);
        if (!removed || m.scienceObjectives.length <= MIN_OBJECTIVES) return m;
        // Drop observation items for the removed objective's measurements (pure id filter),
        // so the plan never references an unknown measurement.
        const dropped = new Set(removed.requiredMeasurements.map((r) => r.id));
        return {
          ...m,
          scienceObjectives: m.scienceObjectives.filter((o) => o.id !== objectiveId),
          operations: {
            ...m.operations,
            observationPlan: m.operations.observationPlan.filter((i) => !dropped.has(i.measurementId)),
          },
        };
      });
    },

    updateOperations(patch) {
      edit((m) => ({ ...m, operations: { ...m.operations, ...patch } }));
    },

    updateConstraints(patch) {
      edit((m) => ({ ...m, constraints: { ...m.constraints, ...patch } }));
    },

    setTrajectory(trajectory, destination) {
      edit((m) => ({ ...m, trajectory, destination }));
      get().commitRevision();
    },

    commitRevision() {
      const { mission, dirty, analysis, pendingChanges, changeLog } = get();
      if (!mission || !dirty) return;
      const next = { ...mission, designRevision: mission.designRevision + 1 };
      const saved = saveMission(next);
      set({
        pendingChanges: [],
        changeLog: [
          ...pendingChanges.map((c) => ({ ...c, revision: next.designRevision })).reverse(),
          ...changeLog,
        ].slice(0, CHANGE_LOG_LIMIT),
        mission: next,
        designRevision: next.designRevision,
        dirty: false,
        status: analysis ? "stale" : "idle",
        saveError: saved.ok ? null : saved.error,
      });
    },

    setCalculating() {
      set({ status: "calculating" });
    },

    applyAnalysis(analysis) {
      const { mission } = get();
      if (!mission || analysis.missionId !== mission.missionId) return false;
      if (analysis.designRevision !== mission.designRevision) return false;
      set({ analysis, analysisRevision: analysis.designRevision, status: "idle" });
      return true;
    },

    setAnalysisError() {
      set({ status: "error" });
    },

    reset() {
      set({ ...EMPTY });
    },
  };
});

// Test hook: lets Playwright exercise store rules directly. Never exposed in production builds.
if (typeof window !== "undefined" && process.env.NODE_ENV !== "production") {
  (window as unknown as { __missionStore?: typeof useMissionStore }).__missionStore = useMissionStore;
}

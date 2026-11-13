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

export type HydrateOutcome =
  | { ok: true }
  | { ok: false; reason: "not-found" | "corrupt" | "unavailable"; message: string };

export interface MissionStoreState {
  mission: MissionState | null;
  designRevision: number;
  analysis: MissionAnalysis | null;
  analysisRevision: number | null;
  status: AnalysisStatus;
  /** True while edits exist that have not been committed as a new revision. */
  dirty: boolean;
  /** Last persistence failure, if any (UI keeps working in memory). */
  saveError: StorageError | null;

  loadTemplate: (scenarioId: ScenarioId, seed?: number) => Promise<LoadOutcome>;
  hydrate: (missionId: string) => HydrateOutcome;
  selectComponent: (category: ComponentCategory, componentId: string) => void;
  updateObjective: (objectiveId: string, patch: Partial<Omit<ScienceObjective, "id">>) => void;
  updateOperations: (patch: Partial<OperationsPlan>) => void;
  updateConstraints: (patch: Partial<MissionConstraints>) => void;
  commitRevision: () => void;
  setCalculating: () => void;
  /** Applies a backend analysis only if it matches the current design revision. */
  applyAnalysis: (analysis: MissionAnalysis) => boolean;
  setAnalysisError: () => void;
  reset: () => void;
}

const EMPTY = {
  mission: null,
  designRevision: 0,
  analysis: null,
  analysisRevision: null,
  status: "idle" as AnalysisStatus,
  dirty: false,
  saveError: null,
};

export const useMissionStore = create<MissionStoreState>()((set, get) => {
  const edit = (change: (m: MissionState) => MissionState) => {
    const { mission } = get();
    if (!mission) return;
    set({ mission: change(mission), dirty: true });
  };

  return {
    ...EMPTY,

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
      const current = get().mission;
      if (current && current.missionId === missionId) return { ok: true };
      if (!isValidMissionId(missionId)) {
        return { ok: false, reason: "not-found", message: "Mission id is not valid." };
      }
      const loaded = loadMission(missionId);
      if (!loaded.ok) {
        const reason = loaded.error.code === "quota" ? "unavailable" : loaded.error.code;
        return { ok: false, reason, message: loaded.error.message };
      }
      set({
        ...EMPTY,
        mission: loaded.value,
        designRevision: loaded.value.designRevision,
      });
      return { ok: true };
    },

    selectComponent(category, componentId) {
      if (category === "instrument") {
        edit((m) => {
          const ids = m.architecture.instrumentIds;
          const next = ids.includes(componentId)
            ? ids.filter((id) => id !== componentId)
            : [...ids, componentId];
          return { ...m, architecture: { ...m.architecture, instrumentIds: next } };
        });
        return;
      }
      const field = SINGLE_SELECT_FIELD[category];
      edit((m) => ({ ...m, architecture: { ...m.architecture, [field]: componentId } }));
    },

    updateObjective(objectiveId, patch) {
      edit((m) => ({
        ...m,
        scienceObjectives: m.scienceObjectives.map((o) =>
          o.id === objectiveId ? { ...o, ...patch } : o,
        ),
      }));
    },

    updateOperations(patch) {
      edit((m) => ({ ...m, operations: { ...m.operations, ...patch } }));
    },

    updateConstraints(patch) {
      edit((m) => ({ ...m, constraints: { ...m.constraints, ...patch } }));
    },

    commitRevision() {
      const { mission, dirty, analysis } = get();
      if (!mission || !dirty) return;
      const next = { ...mission, designRevision: mission.designRevision + 1 };
      const saved = saveMission(next);
      set({
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

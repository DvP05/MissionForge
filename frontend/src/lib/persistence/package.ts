import { API_BASE_URL, apiGet } from "@/lib/api-client";
import type { components } from "@/lib/api/schema";
import { cacheRun, listCachedRuns, type RunData } from "@/lib/persistence/run-cache";
import {
  saveReplayRecord,
  type VersionMismatch,
  type ReplayStatus,
} from "@/lib/persistence/replay";
import { isValidMissionId, loadMission, saveMission } from "@/lib/persistence/storage";
import { useRunStore } from "@/state/run-store";

type Schemas = components["schemas"];
export type MissionPackage = Schemas["MissionPackage"];
export type MissionState = Schemas["MissionState"];
type MissionAnalysis = Schemas["MissionAnalysis"];
type ImportData = Schemas["ImportData"];

export const PACKAGE_SCHEMA_VERSION = "1.0";
/** Must equal the backend `max_import_bytes` (4 MiB): larger files are refused before upload. */
export const MAX_IMPORT_BYTES = 4 * 1024 * 1024;
const IMPORT_TIMEOUT_MS = 30_000;

// ---- Export -------------------------------------------------------------------------------

async function currentManifest(scenarioId: string): Promise<MissionPackage["manifest"]> {
  const [health, templates] = await Promise.all([apiGet("/api/health"), apiGet("/api/templates")]);
  const h = health.ok ? health.data : null;
  return {
    appVersion: h?.appVersion ?? "unknown",
    engineVersion: h?.engineVersion ?? "unknown",
    catalogVersion: h?.catalogVersion ?? "unknown",
    // Run manifests carry each run's own scenario version; this is the mission scenario's current one.
    scenarioVersion:
      (templates.ok && templates.data
        ? templates.data.find((t) => t.scenarioId === scenarioId)?.scenarioVersion
        : undefined) ?? "unknown",
  };
}

export function buildPackage(
  mission: MissionState,
  analysis: MissionAnalysis | null,
  runs: readonly RunData[],
  manifest: MissionPackage["manifest"],
  exportedAt: Date = new Date(),
): MissionPackage {
  return {
    packageSchemaVersion: PACKAGE_SCHEMA_VERSION,
    exportedAt: exportedAt.toISOString(),
    mission,
    // Derived and recalculated on import; only included when it belongs to this revision.
    latestAnalysis: analysis && analysis.designRevision === mission.designRevision ? analysis : null,
    runs: runs.filter((r) => r.run.missionId === mission.missionId).map((r) => r.run),
    evidence: [],
    manifest,
  };
}

/** JSON Blob of the package for this mission (runs come from the browser run cache). */
export async function exportPackage(
  mission: MissionState,
  analysis: MissionAnalysis | null,
): Promise<Blob> {
  const pkg = buildPackage(mission, analysis, listCachedRuns(mission.missionId), await currentManifest(mission.scenarioId));
  return new Blob([JSON.stringify(pkg, null, 2)], { type: "application/json" });
}

export function packageFileName(mission: MissionState): string {
  const slug = mission.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40);
  return `missionforge-${slug || "mission"}-r${mission.designRevision}.json`;
}

export function downloadBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ---- Import -------------------------------------------------------------------------------

export type ImportFailure = { ok: false; code: string; message: string; details?: string[] };

export interface PreparedImport {
  ok: true;
  data: ImportData;
  /** A different saved copy of the same mission id exists locally (replacing it needs consent). */
  conflict: { revision: number; title: string } | null;
}

function failure(code: string, message: string, details?: string[]): ImportFailure {
  return { ok: false, code, message, details };
}

const CODE_MESSAGES: Record<string, string> = {
  INVALID_JSON: "This file is not valid JSON, so it cannot be imported.",
  PAYLOAD_TOO_LARGE: "This file is larger than the 4 MB import limit.",
  UNSUPPORTED_PACKAGE_VERSION: "This package was made with a package format this version cannot read.",
  UNSUPPORTED_SCHEMA_VERSION: "This mission uses a schema version this version cannot read.",
};

/**
 * Size-checks the file and sends it, unmodified, to POST /api/mission/import. Nothing is stored
 * here: the caller applies the result only after `ok: true` (and consent if there is a conflict).
 */
export async function prepareImport(file: File): Promise<PreparedImport | ImportFailure> {
  if (file.size > MAX_IMPORT_BYTES) {
    return failure(
      "FILE_TOO_LARGE",
      `This file is ${(file.size / (1024 * 1024)).toFixed(1)} MB; the import limit is ${MAX_IMPORT_BYTES / (1024 * 1024)} MB. Nothing was changed.`,
    );
  }
  let text: string;
  try {
    text = await file.text();
  } catch {
    return failure("READ_FAILED", "The file could not be read. Nothing was changed.");
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), IMPORT_TIMEOUT_MS);
  let body: unknown;
  try {
    const res = await fetch(`${API_BASE_URL}/api/mission/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: text,
      signal: controller.signal,
    });
    try {
      body = await res.json();
    } catch {
      return failure("NON_JSON_RESPONSE", "The server answered unexpectedly. Nothing was changed.");
    }
  } catch {
    return failure(
      "NETWORK_ERROR",
      "The backend could not be reached, so the file could not be checked. Nothing was changed.",
    );
  } finally {
    clearTimeout(timer);
  }
  const env = body as {
    ok?: boolean;
    data?: ImportData | null;
    error?: { code: string; message: string; details?: { fields?: { path: string; message: string }[] } | null } | null;
  };
  if (!env || env.ok !== true || !env.data) {
    const code = env?.error?.code ?? "IMPORT_REJECTED";
    const fields = env?.error?.details?.fields ?? [];
    return failure(
      code,
      `${CODE_MESSAGES[code] ?? env?.error?.message ?? "The file was rejected."} Nothing was changed.`,
      fields.slice(0, 5).map((f) => `${f.path || "package"}: ${f.message}`),
    );
  }
  const mission = env.data.package.mission;
  if (!isValidMissionId(mission.missionId)) {
    return failure("INVALID_PACKAGE", "The package mission id is not valid. Nothing was changed.");
  }
  const existing = loadMission(mission.missionId);
  const differs = existing.ok && JSON.stringify(existing.value) !== JSON.stringify(mission);
  return {
    ok: true,
    data: env.data,
    conflict: differs ? { revision: existing.value.designRevision, title: existing.value.title } : null,
  };
}

export interface AppliedImport {
  ok: true;
  missionId: string;
  runs: { runId: string; status: ReplayStatus; mismatches: VersionMismatch[]; stored: boolean }[];
}

/** Writes the validated mission and its runs; the mission is written first so a quota failure changes nothing. */
export function applyImport(prepared: PreparedImport): AppliedImport | ImportFailure {
  const { package: pkg, replay } = prepared.data;
  const saved = saveMission(pkg.mission);
  if (!saved.ok) {
    return failure(
      "STORAGE_FAILED",
      "Browser storage is full or unavailable, so the import could not be saved. Your current mission was not changed.",
    );
  }
  const statusById = new Map(replay.map((r) => [r.runId, r]));
  const runs: AppliedImport["runs"] = [];
  for (const run of pkg.runs ?? []) {
    const st = statusById.get(run.runId);
    if (!st) continue;
    saveReplayRecord(run.runId, { status: st.status, mismatches: st.mismatches, source: "import" });
    let stored = false;
    if (st.analysis) {
      const data: RunData = {
        analysis: st.analysis,
        run,
        telemetry: run.telemetry,
        events: run.events,
        finalReport: run.finalReport,
        notes:
          st.status === "version-mismatch"
            ? ["Imported run. Its analysis was recalculated by this engine and may differ from the original."]
            : ["Imported run."],
      };
      stored = cacheRun(data);
      if (stored) useRunStore.setState((s) => ({ runs: { ...s.runs, [run.runId]: data } }));
    }
    runs.push({ runId: run.runId, status: st.status, mismatches: st.mismatches, stored });
  }
  return { ok: true, missionId: pkg.mission.missionId, runs };
}

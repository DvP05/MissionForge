import { apiPost } from "@/lib/api-client";
import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type MissionRun = Schemas["MissionRun"];
export type VersionMismatch = Schemas["VersionMismatchItem"];
/** Server answers of POST /api/mission/replay. Only `identical-replay` proves identity. */
export type ReplayStatus = Schemas["ReplayData"]["status"];
/** Import-time statuses add `replayable`: versions match, replay can be verified (not a proof). */
export type RecordStatus = ReplayStatus | Schemas["RunReplayStatus"]["status"];

/** Versions this app (backend) uses right now, from GET /api/health. */
export interface CurrentVersions {
  engineVersion: string;
  catalogVersion: string;
  schemaVersion: string;
}

/**
 * Client-side manifest comparison, for display before the server has been asked.
 * It can only prove a MISMATCH (or "versions look equal"): it cannot see the scenario version
 * or whether the event set still exists, so a server replay (`replayRun`) is what establishes
 * an identical replay. It never returns an identity claim.
 */
export function clientMismatches(
  run: Pick<MissionRun, "manifest">,
  current: CurrentVersions,
): VersionMismatch[] {
  const m = run.manifest;
  const pairs: [string, string, string][] = [
    ["engineVersion", m.engineVersion, current.engineVersion],
    ["catalogVersion", m.catalogVersion, current.catalogVersion],
    ["schemaVersion", m.schemaVersion, current.schemaVersion],
  ];
  return pairs.filter(([, rec, cur]) => rec !== cur).map(([field, recorded, cur]) => ({ field, recorded, current: cur }));
}

export function replayStatus(
  run: Pick<MissionRun, "manifest">,
  current: CurrentVersions,
): "versions-match" | "version-mismatch" {
  return clientMismatches(run, current).length === 0 ? "versions-match" : "version-mismatch";
}

export function describeMismatches(items: readonly VersionMismatch[]): string {
  return items.map((m) => `${m.field}: recorded ${m.recorded}, this server ${m.current}`).join("; ");
}

/** What the UI says about a status. "Identical" appears ONLY for a server-confirmed status. */
export function statusLabel(status: RecordStatus, mismatches: readonly VersionMismatch[]): string {
  if (status === "replayable") return "Versions match \u2014 replay can be verified";
  if (status === "identical-replay") return "Identical replay (verified by re-running)";
  if (status === "diverged") {
    return "Not an identical replay: re-running with the same versions produced a different result";
  }
  const why = mismatches.length ? `: ${describeMismatches(mismatches)}` : "";
  return `Version mismatch — not an identical replay${why}`;
}

export interface ReplayRecord {
  status: RecordStatus;
  mismatches: VersionMismatch[];
  source: "import" | "replay";
}

export const REPLAY_KEY_PREFIX = "missionforge:replay:";

function storage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function saveReplayRecord(runId: string, record: ReplayRecord): void {
  try {
    storage()?.setItem(REPLAY_KEY_PREFIX + runId, JSON.stringify(record));
  } catch {
    /* status is re-derivable by replaying again */
  }
}

export function clearReplayRecord(runId: string): void {
  try {
    storage()?.removeItem(REPLAY_KEY_PREFIX + runId);
  } catch {
    /* ignore */
  }
}

export function loadReplayRecord(runId: string): ReplayRecord | null {
  try {
    const raw = storage()?.getItem(REPLAY_KEY_PREFIX + runId);
    if (!raw) return null;
    const v: unknown = JSON.parse(raw);
    if (typeof v !== "object" || v === null) return null;
    const r = v as Partial<ReplayRecord>;
    if (
      (r.status !== "replayable" && r.status !== "identical-replay" && r.status !== "version-mismatch" && r.status !== "diverged") ||
      !Array.isArray(r.mismatches) ||
      (r.source !== "import" && r.source !== "replay")
    ) {
      return null;
    }
    return { status: r.status, mismatches: r.mismatches, source: r.source };
  } catch {
    return null;
  }
}

export type ReplayResult =
  | { ok: true; status: ReplayStatus; mismatches: VersionMismatch[]; run: MissionRun | null }
  | { ok: false; message: string };

/** Asks the server to re-run a recorded run (POST /api/mission/replay) and records the answer. */
export async function replayRun(run: MissionRun): Promise<ReplayResult> {
  const res = await apiPost("/api/mission/replay", { run }, { timeoutMs: 30_000 });
  if (!res.ok || !res.data) {
    return { ok: false, message: res.error?.message ?? "The replay could not be run." };
  }
  const { status, mismatches, run: rebuilt } = res.data;
  saveReplayRecord(run.runId, { status, mismatches, source: "replay" });
  return { ok: true, status, mismatches, run: rebuilt ?? null };
}

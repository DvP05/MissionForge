import type { components } from "@/lib/api/schema";

export type RunData = components["schemas"]["SimulateData"];

/** Minimal client cache of immutable runs (Task 4.5 adds full persistence and manifests). */
export const RUN_KEY_PREFIX = "missionforge:run:";
const RUN_ID_PATTERN = /^[A-Za-z0-9_-]{1,80}$/;
const MAX_CACHED_RUNS = 6;

export const isValidRunId = (id: string): boolean => RUN_ID_PATTERN.test(id);

function storage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

function runKeys(s: Storage): string[] {
  const keys: string[] = [];
  for (let i = 0; i < s.length; i += 1) {
    const k = s.key(i);
    if (k && k.startsWith(RUN_KEY_PREFIX)) keys.push(k);
  }
  return keys;
}

function looksLikeRun(v: unknown, runId: string): v is RunData {
  if (typeof v !== "object" || v === null) return false;
  const run = (v as { run?: { runId?: unknown; events?: unknown; telemetry?: unknown } }).run;
  return (
    !!run &&
    run.runId === runId &&
    Array.isArray(run.events) &&
    Array.isArray(run.telemetry) &&
    typeof (v as { analysis?: unknown }).analysis === "object"
  );
}

export function loadCachedRun(runId: string): RunData | null {
  if (!isValidRunId(runId)) return null;
  const s = storage();
  if (!s) return null;
  try {
    const raw = s.getItem(RUN_KEY_PREFIX + runId);
    if (raw === null) return null;
    const parsed: unknown = JSON.parse(raw);
    return looksLikeRun(parsed, runId) ? parsed : null;
  } catch {
    return null;
  }
}

/** Best effort: on quota failure older cached runs are dropped, then it gives up silently. */
export function cacheRun(data: RunData): void {
  const id = data.run.runId;
  if (!isValidRunId(id)) return;
  const s = storage();
  if (!s) return;
  const key = RUN_KEY_PREFIX + id;
  const json = JSON.stringify(data);
  try {
    const others = runKeys(s).filter((k) => k !== key);
    while (others.length >= MAX_CACHED_RUNS) s.removeItem(others.shift() as string);
    s.setItem(key, json);
  } catch {
    try {
      runKeys(s).filter((k) => k !== key).forEach((k) => s.removeItem(k));
      s.setItem(key, json);
    } catch {
      /* storage unavailable or full: the run stays in memory and can be re-fetched */
    }
  }
}

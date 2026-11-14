import type { components } from "@/lib/api/schema";

export type RunData = components["schemas"]["SimulateData"];

/** Client cache of immutable runs (bounded LRU; export packages include these runs). */
export const RUN_KEY_PREFIX = "missionforge:run:";
const INDEX_KEY = "missionforge:run-index";
const RUN_ID_PATTERN = /^[A-Za-z0-9_-]{1,80}$/;
const MAX_CACHED_RUNS = 6;

export const isValidRunId = (id: string): boolean => RUN_ID_PATTERN.test(id);

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const isArr = (v: unknown): v is unknown[] => Array.isArray(v);
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isStr = (v: unknown): v is string => typeof v === "string";

/**
 * Structural check of every field the mission-control and review renderers read.
 * Anything that fails is treated as absent (cache) or as an unusable response (GET).
 */
export function isValidRunData(v: unknown, runId?: string): v is RunData {
  if (!isObj(v) || !isObj(v.run) || !isObj(v.analysis)) return false;
  const run = v.run;
  if (!isStr(run.runId) || (runId !== undefined && run.runId !== runId)) return false;
  if (!isNum(run.seed) || typeof run.experimental !== "boolean" || !isStr(run.engineVersion)) return false;
  if (!isArr(run.phases) || !run.phases.every(isStr)) return false;
  if (!isArr(run.phaseTransitions) || !run.phaseTransitions.every((t) => isObj(t) && isStr(t.phase) && isNum(t.missionDay))) return false;
  if (
    !isArr(run.events) ||
    !run.events.every(
      (e) =>
        isObj(e) &&
        isStr(e.id) &&
        isNum(e.missionDay) &&
        isNum(e.sequence) &&
        isStr(e.title) &&
        isStr(e.description) &&
        isStr(e.severity) &&
        isStr(e.type) &&
        isObj(e.trigger) &&
        isArr(e.choices) &&
        e.choices.every((c) => isObj(c) && isStr(c.id) && isStr(c.label) && isStr(c.tradeoff)),
    )
  ) {
    return false;
  }
  if (
    !isArr(run.telemetry) ||
    !run.telemetry.every((s) => isObj(s) && isStr(s.channel) && isStr(s.unit) && isStr(s.fidelity) && isNum(s.missionDay) && isNum(s.value))
  ) {
    return false;
  }
  if (
    !isArr(run.decisions) ||
    !run.decisions.every((d) => isObj(d) && isStr(d.eventId) && isStr(d.choiceId) && isStr(d.decisionMaker) && isNum(d.missionDay))
  ) {
    return false;
  }
  if (
    !isArr(run.scienceOutcomes) ||
    !run.scienceOutcomes.every(
      (o) => isObj(o) && isStr(o.objectiveId) && isStr(o.status) && isNum(o.collectedFraction) && isNum(o.returnedFraction),
    )
  ) {
    return false;
  }
  const report = run.finalReport;
  if (
    !isObj(report) ||
    !isStr(report.outcome) ||
    !isStr(report.summary) ||
    !isArr(report.rootCauses) ||
    !isArr(report.counterfactuals) ||
    !isArr(report.limitations) ||
    !isObj(report.score) ||
    !isNum(report.score.total) ||
    !isArr(report.score.dimensions) ||
    !report.score.dimensions.every((d) => isObj(d) && isStr(d.id) && isNum(d.score) && isNum(d.weight) && isStr(d.explanation))
  ) {
    return false;
  }
  const snapshot = run.inputSnapshot;
  if (!isObj(snapshot) || !isArr(snapshot.scienceObjectives) || !snapshot.scienceObjectives.every((o) => isObj(o) && isStr(o.id) && isStr(o.title))) {
    return false;
  }
  const analysis = v.analysis;
  return (
    isArr(analysis.constraints) &&
    analysis.constraints.every((c) => isObj(c) && isStr(c.id) && isStr(c.status)) &&
    isObj(analysis.budgets) &&
    isObj(analysis.science) &&
    isObj(analysis.score) &&
    isStr(analysis.engineVersion)
  );
}

function storage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

/** Run ids ordered least recently used first. */
function readIndex(s: Storage): string[] {
  try {
    const parsed: unknown = JSON.parse(s.getItem(INDEX_KEY) ?? "[]");
    return isArr(parsed) ? parsed.filter((x): x is string => isStr(x) && isValidRunId(x)) : [];
  } catch {
    return [];
  }
}

function writeIndex(s: Storage, ids: string[]): void {
  try {
    s.setItem(INDEX_KEY, JSON.stringify(ids));
  } catch {
    /* index is best effort */
  }
}

/**
 * Brings the LRU index in line with what is actually stored: run entries written before the
 * index existed (legacy, Task 4.4 minor) are adopted as least recently used, ids whose entry is
 * gone are dropped, and the bound is enforced by evicting the oldest. Once per page session.
 */
let reconciled = false;
function reconcileIndex(s: Storage): void {
  if (reconciled) return;
  reconciled = true;
  try {
    const stored = new Set<string>();
    for (let i = 0; i < s.length; i += 1) {
      const key = s.key(i);
      if (key?.startsWith(RUN_KEY_PREFIX)) {
        const id = key.slice(RUN_KEY_PREFIX.length);
        if (isValidRunId(id)) stored.add(id);
      }
    }
    const indexed = readIndex(s).filter((id) => stored.has(id));
    const order = [...[...stored].filter((id) => !indexed.includes(id)), ...indexed];
    while (order.length > MAX_CACHED_RUNS) s.removeItem(RUN_KEY_PREFIX + (order.shift() as string));
    writeIndex(s, order);
  } catch {
    /* best effort */
  }
}

function touch(s: Storage, id: string): string[] {
  const ids = readIndex(s).filter((x) => x !== id);
  ids.push(id);
  writeIndex(s, ids);
  return ids;
}

function dropRun(s: Storage, id: string): void {
  try {
    s.removeItem(RUN_KEY_PREFIX + id);
    writeIndex(s, readIndex(s).filter((x) => x !== id));
  } catch {
    /* ignore */
  }
}

/** Reads a cached run and marks it recently used; an invalid entry is discarded. */
export function loadCachedRun(runId: string): RunData | null {
  if (!isValidRunId(runId)) return null;
  const s = storage();
  if (!s) return null;
  reconcileIndex(s);
  try {
    const raw = s.getItem(RUN_KEY_PREFIX + runId);
    if (raw === null) return null;
    const parsed: unknown = JSON.parse(raw);
    if (isValidRunData(parsed, runId)) {
      touch(s, runId);
      return parsed;
    }
  } catch {
    /* fall through: unreadable entry */
  }
  dropRun(s, runId);
  return null;
}

/** Cached runs of one mission (newest first by LRU order). Invalid entries are dropped. */
export function listCachedRuns(missionId: string): RunData[] {
  const s = storage();
  if (!s) return [];
  reconcileIndex(s);
  const out: RunData[] = [];
  for (const id of readIndex(s).reverse()) {
    try {
      const raw = s.getItem(RUN_KEY_PREFIX + id);
      const parsed: unknown = raw === null ? null : JSON.parse(raw);
      if (isValidRunData(parsed, id)) {
        if (parsed.run.missionId === missionId) out.push(parsed);
      } else {
        dropRun(s, id);
      }
    } catch {
      dropRun(s, id);
    }
  }
  return out;
}

/** Best effort, least-recently-used eviction; on quota failure it drops older runs then gives up. Returns whether the run was stored. */
export function cacheRun(data: RunData): boolean {
  const id = data.run.runId;
  if (!isValidRunId(id)) return false;
  const s = storage();
  if (!s) return false;
  reconcileIndex(s);
  const json = JSON.stringify(data);
  try {
    const order = readIndex(s).filter((x) => x !== id);
    while (order.length >= MAX_CACHED_RUNS) s.removeItem(RUN_KEY_PREFIX + (order.shift() as string));
    s.setItem(RUN_KEY_PREFIX + id, json);
    order.push(id);
    writeIndex(s, order);
    return true;
  } catch {
    try {
      for (const other of readIndex(s).filter((x) => x !== id)) s.removeItem(RUN_KEY_PREFIX + other);
      s.setItem(RUN_KEY_PREFIX + id, json);
      writeIndex(s, [id]);
      return true;
    } catch {
      /* storage unavailable or full: the run stays in memory and can be re-fetched */
      return false;
    }
  }
}

export const MAX_CACHED_RUN_COUNT = MAX_CACHED_RUNS;

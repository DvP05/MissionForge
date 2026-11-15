/**
 * Player progression (design_update.md section 7). Every stage, badge and challenge is computed
 * from real product state: the saved MissionState, the backend analysis of the current
 * revision, cached runs, and a few recorded player actions (ran a trade study, opened the
 * review). Nothing rewards spending, and no gate can be passed by clicking: a FAIL stays a FAIL.
 * Progress is presentation-only and lives in this browser, next to the saved mission.
 */
import type { components } from "@/lib/api/schema";
import { evaluateGates } from "@/lib/spacecraft/gates";

type Schemas = components["schemas"];
type MissionState = Schemas["MissionState"];
type MissionAnalysis = Schemas["MissionAnalysis"];

export type ProgressFlag = "tradeStudy" | "riskReviewed" | "reviewOpened" | "dossierExported" | "powerRecovered";

export interface ProgressRecord {
  flags: Partial<Record<ProgressFlag, number>>;
  /** Badge id -> design revision at which it was first earned. */
  badges: Record<string, number>;
}

const KEY = "missionforge:progress:";
export const PROGRESS_EVENT = "missionforge:progress";

export function readProgress(missionId: string): ProgressRecord {
  try {
    const raw = window.localStorage.getItem(KEY + missionId);
    const v = raw ? (JSON.parse(raw) as Partial<ProgressRecord>) : {};
    return { flags: v.flags && typeof v.flags === "object" ? v.flags : {}, badges: v.badges && typeof v.badges === "object" ? v.badges : {} };
  } catch {
    return { flags: {}, badges: {} };
  }
}

function write(missionId: string, record: ProgressRecord): void {
  try {
    window.localStorage.setItem(KEY + missionId, JSON.stringify(record));
  } catch {
    /* storage unavailable: progress lasts for this page view only */
  }
  window.dispatchEvent(new CustomEvent(PROGRESS_EVENT, { detail: missionId }));
}

/** Record a real player action (a completed trade study, an opened review, ...). */
export function recordProgress(missionId: string, flag: ProgressFlag, revision: number): void {
  if (typeof window === "undefined") return;
  const r = readProgress(missionId);
  if (r.flags[flag] !== undefined) return;
  r.flags[flag] = revision;
  write(missionId, r);
}

export function recordBadges(missionId: string, ids: string[], revision: number): string[] {
  const r = readProgress(missionId);
  const fresh = ids.filter((id) => r.badges[id] === undefined);
  if (fresh.length === 0) return [];
  for (const id of fresh) r.badges[id] = revision;
  write(missionId, r);
  return fresh;
}

export type StageStatus = "complete" | "current" | "attention" | "todo";

export interface Stage {
  id: string;
  title: string;
  objective: string;
  status: StageStatus;
  /** Why it is not complete yet (from real state). */
  detail: string;
  href: string;
}

export interface ProgressInput {
  mission: MissionState;
  /** Backend analysis of the CURRENT revision, or null (none yet / stale). */
  analysis: MissionAnalysis | null;
  runIds: string[];
  record: ProgressRecord;
}

const ok = (a: MissionAnalysis | null, id: string) => a?.constraints.find((c) => c.id === id)?.status === "pass";

/** The eight mission stages (design_update.md 7.1), each completed by real state only. */
export function computeStages({ mission, analysis, runIds, record }: ProgressInput): Stage[] {
  const id = mission.missionId;
  const lastRun = runIds[runIds.length - 1];
  const gates = analysis ? evaluateGates(analysis.constraints) : [];
  const failing = gates.filter((g) => g.status === "FAIL");
  const a = mission.architecture;
  const built = [a.launchVehicleId, a.busId, a.propulsionId, a.powerId, a.adcsId, a.communicationsId, a.thermalId, a.cdhId, a.groundSegmentId].every(Boolean) && a.instrumentIds.length > 0;
  const objectivesOk = mission.scienceObjectives.length >= 2 && mission.scienceObjectives.length <= 4;

  const raw: Omit<Stage, "status">[] = [
    { id: "accept", title: "Accept the mission", objective: "Read the brief: target, science question, top constraints.", detail: "Mission accepted.", href: `/mission/${id}` },
    { id: "science", title: "Define the science", objective: "Keep 2–4 objectives with their required measurements.", detail: objectivesOk ? `${mission.scienceObjectives.length} objectives selected.` : "Choose between two and four objectives.", href: `/science/${id}` },
    { id: "build", title: "Build the spacecraft", objective: "Fill every subsystem and install at least one instrument.", detail: built ? "Every subsystem is filled." : "A subsystem is empty or no instrument is installed.", href: `/architect/${id}` },
    { id: "gates", title: "Close the engineering gates", objective: "Clear every FAIL gate; review each WATCH.", detail: !analysis ? "Waiting for the engine analysis of this revision." : failing.length ? `${failing.length} gate(s) failing: ${failing.map((g) => g.gate.label).join(", ")}.` : "No gate is failing.", href: `/readiness/${id}` },
    { id: "trade", title: "Run the trade study", objective: "Compare alternatives or explore the Pareto front.", detail: record.flags.tradeStudy !== undefined ? "A trade study has been run." : "No trade study run yet.", href: `/arena/${id}` },
    { id: "readiness", title: "Pass the readiness review", objective: "The engine reports the design mission-ready.", detail: !analysis ? "Waiting for the engine analysis." : analysis.missionReady ? "Mission-ready." : "The engine does not report this design mission-ready yet.", href: `/readiness/${id}` },
    { id: "fly", title: "Fly the mission", objective: "Launch a deterministic run and operate it.", detail: lastRun ? `${runIds.length} run(s) flown.` : "Not flown yet.", href: lastRun ? `/control/${lastRun}` : `/architect/${id}` },
    { id: "review", title: "Review the outcome", objective: "Open the debrief and export the evidence passport.", detail: record.flags.dossierExported !== undefined ? "Debrief done and passport exported." : record.flags.reviewOpened !== undefined ? "Debrief opened; export the passport to finish." : "No debrief yet.", href: lastRun ? `/review/${lastRun}` : `/architect/${id}` },
  ];

  const done: Record<string, boolean> = {
    accept: true,
    science: objectivesOk,
    build: built,
    gates: analysis !== null && failing.length === 0,
    trade: record.flags.tradeStudy !== undefined,
    readiness: analysis?.missionReady === true,
    fly: runIds.length > 0,
    review: record.flags.dossierExported !== undefined,
  };
  const attention: Record<string, boolean> = { gates: failing.length > 0, build: !built };
  let currentAssigned = false;
  return raw.map((s) => {
    let status: StageStatus = done[s.id] ? "complete" : attention[s.id] ? "attention" : "todo";
    if (!done[s.id] && !currentAssigned) {
      currentAssigned = true;
      if (status === "todo") status = "current";
    }
    return { ...s, status };
  });
}

export interface Badge {
  id: string;
  title: string;
  why: string;
}

export const BADGES: Badge[] = [
  { id: "science-traceable", title: "Science Traceable", why: "The engine reports mandatory science coverage passing." },
  { id: "power-recovered", title: "Power Margin Recovered", why: "Energy closure went from failing or watch to pass after your change." },
  { id: "downlink-ready", title: "Downlink Plan Ready", why: "Link margin, data return and data buffer all pass." },
  { id: "risk-reviewed", title: "Risk Reviewed", why: "You ran the robustness lab on this mission." },
  { id: "mission-ready", title: "Mission Ready", why: "The engine reports the design mission-ready." },
];

/** Badges the current state earns (never for spending: each needs a passing engine result). */
export function earnedBadges(analysis: MissionAnalysis | null, previous: MissionAnalysis | null, record: ProgressRecord): string[] {
  const out: string[] = [];
  if (ok(analysis, "science-mandatory-coverage")) out.push("science-traceable");
  const before = previous?.constraints.find((c) => c.id === "energy-closure")?.status;
  if (ok(analysis, "energy-closure") && (before === "fail" || before === "warning")) out.push("power-recovered");
  if (ok(analysis, "link-margin") && ok(analysis, "data-return") && ok(analysis, "data-buffer")) out.push("downlink-ready");
  if (record.flags.riskReviewed !== undefined) out.push("risk-reviewed");
  if (analysis?.missionReady) out.push("mission-ready");
  return out;
}

export interface Challenge {
  id: string;
  title: string;
  /** Evaluated from engine results only; null when the needed result is not modelled. */
  met: boolean | null;
  basis: string;
}

/** Optional mastery challenges (design_update.md 7.3), each from real constraint results. */
export function challenges(analysis: MissionAnalysis | null): Challenge[] {
  const st = (id: string) => analysis?.constraints.find((c) => c.id === id)?.status;
  const evalAll = (ids: string[]) => {
    if (!analysis) return null;
    const s = ids.map(st);
    if (s.some((x) => x === undefined || x === "not-modelled")) return null;
    return s.every((x) => x === "pass");
  };
  return [
    { id: "science-under-cap", title: "Meet the science target under the launch-mass cap", met: evalAll(["science-minimum-score", "mass-launch-limit"]), basis: "science-minimum-score and mass-launch-limit both pass" },
    { id: "every-bit-home", title: "Bring every bit home", met: evalAll(["data-return", "data-buffer", "link-margin"]), basis: "data-return, data-buffer and link-margin all pass" },
    { id: "lean-and-ready", title: "Mission-ready within budget", met: analysis ? analysis.missionReady && st("budget") === "pass" : null, basis: "mission-ready and the budget constraint passes" },
  ];
}

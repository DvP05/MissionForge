import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type MissionEvent = Schemas["MissionEvent"];
export type MissionRun = Schemas["MissionRun"];
export type DecisionRecord = Schemas["DecisionRecord"];
export type TelemetrySample = Schemas["TelemetrySample"];
export type Phase = MissionRun["phases"][number];

/**
 * Display pacing only: mission days shown per wall-clock second at 1x. The speed
 * multiplier changes how fast the immutable run is revealed, never what it contains.
 */
export const DAYS_PER_SECOND = 100;
export const SPEEDS = [0.5, 1, 4] as const;
export type Speed = (typeof SPEEDS)[number];

/** Events in backend order (missionDay, then sequence). Pure view over the immutable run. */
export function sortedEvents(run: MissionRun): MissionEvent[] {
  return [...run.events].sort((a, b) => a.missionDay - b.missionDay || a.sequence - b.sequence);
}

export function runDuration(run: MissionRun): number {
  let end = 0;
  for (const e of run.events) end = Math.max(end, e.missionDay);
  for (const t of run.telemetry) end = Math.max(end, t.missionDay);
  for (const p of run.phaseTransitions) end = Math.max(end, p.missionDay);
  return end;
}

/** True while the player has not made the choice for this decision event. */
export function isUndecided(event: MissionEvent, decisions: DecisionRecord[]): boolean {
  return (
    event.choices.length > 0 &&
    !decisions.some((d) => d.eventId === event.id && d.decisionMaker === "player")
  );
}

/** The first undecided decision at or before `day`, when the decision gate is armed. */
export function pendingDecision(
  events: MissionEvent[],
  decisions: DecisionRecord[],
  day: number,
  armed: boolean,
): MissionEvent | null {
  if (!armed) return null;
  return events.find((e) => e.missionDay <= day && isUndecided(e, decisions)) ?? null;
}

export function nextDecisionDay(events: MissionEvent[], decisions: DecisionRecord[], day: number): number | null {
  const e = events.find((x) => x.missionDay > day && isUndecided(x, decisions));
  return e ? e.missionDay : null;
}

export function nextEventDay(events: MissionEvent[], day: number): number | null {
  const e = events.find((x) => x.missionDay > day);
  return e ? e.missionDay : null;
}

/**
 * Advances the display position by `dtSeconds` of wall-clock time. Stops exactly at the
 * next undecided decision (when armed) and at the end of the run. No physics, no outcomes.
 */
export function advance(args: {
  day: number;
  dtSeconds: number;
  speed: number;
  duration: number;
  events: MissionEvent[];
  decisions: DecisionRecord[];
  armed: boolean;
}): { day: number; stoppedAtDecision: boolean; finished: boolean } {
  const target = Math.min(args.duration, args.day + args.dtSeconds * args.speed * DAYS_PER_SECOND);
  if (args.armed) {
    const stop = nextDecisionDay(args.events, args.decisions, args.day);
    if (stop !== null && stop <= target) return { day: stop, stoppedAtDecision: true, finished: false };
  }
  return { day: target, stoppedAtDecision: false, finished: target >= args.duration };
}

export function visibleEvents(events: MissionEvent[], day: number): MissionEvent[] {
  return events.filter((e) => e.missionDay <= day);
}

export function currentPhase(run: MissionRun, day: number): Phase | null {
  let phase: Phase | null = null;
  for (const t of run.phaseTransitions) if (t.missionDay <= day) phase = t.phase;
  return phase;
}

export interface ChannelSnapshot {
  channel: string;
  latest: TelemetrySample;
  previous: TelemetrySample | null;
}

/** Latest and previous sample per channel up to `day`; samples are passed through untouched. */
export function channelSnapshots(samples: TelemetrySample[], day: number): Map<string, ChannelSnapshot> {
  const out = new Map<string, ChannelSnapshot>();
  for (const s of samples) {
    if (s.missionDay > day) continue;
    const prev = out.get(s.channel);
    out.set(s.channel, { channel: s.channel, latest: s, previous: prev ? prev.latest : null });
  }
  return out;
}

export type Trend = "rising" | "falling" | "steady" | "no-trend";

export function trendOf(snap: ChannelSnapshot): Trend {
  if (!snap.previous) return "no-trend";
  if (snap.latest.value > snap.previous.value) return "rising";
  if (snap.latest.value < snap.previous.value) return "falling";
  return "steady";
}

/** Channel order as the backend emits them first (stable, derived from the data itself). */
export function channelIds(samples: TelemetrySample[]): string[] {
  const seen: string[] = [];
  for (const s of samples) if (!seen.includes(s.channel)) seen.push(s.channel);
  return seen;
}

export interface DesignLimit {
  value: number;
  unit: string;
  provenance: components["schemas"]["Provenance"];
}

/**
 * The design-time link-margin limit: the `limit` Quantity of the run's input-analysis
 * `link-margin` constraint. Absent (null) when the analysis has no modelled limit.
 */
export function linkMarginLimit(analysis: components["schemas"]["MissionAnalysis"]): DesignLimit | null {
  const q = analysis.constraints.find((c) => c.id === "link-margin")?.limit;
  if (!q || !Number.isFinite(q.value) || q.provenance.fidelity === "not-modelled") return null;
  return { value: q.value, unit: q.unit, provenance: q.provenance };
}

export const PHASE_LABEL: Record<Phase, string> = {
  "pre-launch": "Pre-launch",
  "launch-deployment": "Launch and deployment",
  commissioning: "Commissioning",
  cruise: "Cruise",
  "mid-course": "Mid-course",
  approach: "Approach",
  "science-ops": "Science operations",
  "downlink-return": "Downlink and return",
  complete: "Complete",
  terminated: "Terminated",
};

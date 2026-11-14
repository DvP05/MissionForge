import type { components } from "@/lib/api/schema";
import type { MissionEvent, MissionRun } from "./playback";

export type AutonomyDecision = components["schemas"]["AutonomyDecision"];

export interface ContactSpan {
  index: number;
  start: number; // mission day
  end: number;
}

const MINUTES_PER_DAY = 1440;

/** Planned contacts minus the ones the run's log says were missed (presentation only). */
export function flownContacts(run: MissionRun): ContactSpan[] {
  const missed = new Set(
    run.events
      .filter((e: MissionEvent) => e.type === "downlink" && e.title.includes("missed"))
      .map((e) => String(e.trigger["plan_item"] ?? "")),
  );
  return run.inputSnapshot.operations.downlinkPlan
    .map((d, index) => ({ index, start: d.startDay, end: d.startDay + d.durationMinutes / MINUTES_PER_DAY }))
    .filter((c) => !missed.has(`operations.downlinkPlan[${c.index}]`));
}

export interface Authority {
  mode: "ground" | "onboard";
  /** Days until the next contact opens (onboard), or until the current one closes (ground). */
  untilDays: number | null;
}

export function authorityAt(contacts: ContactSpan[], day: number): Authority {
  const now = contacts.find((c) => c.start <= day && day <= c.end);
  if (now) return { mode: "ground", untilDays: now.end - day };
  const next = contacts.filter((c) => c.start > day).sort((a, b) => a.start - b.start)[0];
  return { mode: "onboard", untilDays: next ? next.start - day : null };
}

/** Mission day of an autonomy decision: the planned observation its candidates refer to. */
export function decisionDay(run: MissionRun, d: AutonomyDecision): number | null {
  const id = d.selectedActionId ?? d.candidates[0]?.actionId;
  const idx = id ? Number(id.split(":")[1]) : NaN;
  const item = Number.isInteger(idx) ? run.inputSnapshot.operations.observationPlan[idx] : undefined;
  return item ? item.startDay : null;
}

export const POLICY_LABEL: Record<AutonomyDecision["policy"], string> = {
  conservative: "Conservative",
  "science-first": "Science-first",
  "resource-aware": "Resource-aware",
};

"use client";

import { Radio, Satellite } from "lucide-react";

import { formatNumber } from "@/lib/format";
import { authorityAt, POLICY_LABEL, type AutonomyDecision, type ContactSpan } from "./authority";

/**
 * Task 6.5: who commands the spacecraft right now. Contact windows are the run's flown
 * ground passes (scenario data); outside them the onboard policy decides.
 */
export function AuthorityBanner({
  contacts,
  day,
  policy,
}: {
  contacts: ContactSpan[];
  day: number;
  policy: AutonomyDecision["policy"] | null;
}) {
  const a = authorityAt(contacts, day);
  const ground = a.mode === "ground";
  const Icon = ground ? Radio : Satellite;
  return (
    <section
      data-testid="authority-banner"
      data-mode={a.mode}
      aria-live="polite"
      className={`flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl border px-4 py-3 ${
        ground ? "border-accent-cyan/50 bg-accent-cyan/5" : "border-accent-amber/60 bg-accent-amber/5"
      }`}
    >
      <span className={`flex items-center gap-2 font-mono text-sm font-semibold tracking-wide ${ground ? "text-accent-cyan" : "text-accent-amber"}`}>
        <Icon aria-hidden className="h-4 w-4" />
        {ground ? "GROUND CONTROL" : "ONBOARD AUTONOMY"}
      </span>
      <span data-testid="authority-countdown" className="text-sm">
        {ground
          ? `In contact: the pass closes in ${formatNumber(a.untilDays ?? 0)} d.`
          : a.untilDays !== null
            ? `Communication blackout: next contact in ${formatNumber(a.untilDays)} d. Ground commands cannot reach the spacecraft.`
            : "Communication blackout: no further contact is planned."}
      </span>
      {policy ? (
        <span className="text-xs text-muted">Onboard policy: {POLICY_LABEL[policy]} (from the safe-mode setting)</span>
      ) : null}
    </section>
  );
}

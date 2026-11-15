"use client";

import { useMemo, useSyncExternalStore } from "react";

import { ReadinessSummary } from "@/components/progress/ReadinessSummary";
import { ACTIVE_MISSION_EVENT, readActiveMission } from "@/lib/persistence/active-mission";
import { loadMission } from "@/lib/persistence/storage";
import { formatQuantity } from "@/lib/format";
import { useMissionStore } from "@/state/mission-store";

function Readout({ label, value, testId }: { label: string; value: string; testId?: string }) {
  return (
    <div className="flex min-w-0 flex-col">
      <span className="label-caps text-muted">{label}</span>
      <span data-testid={testId} className="truncate font-mono text-sm font-semibold text-foreground">
        {value}
      </span>
    </div>
  );
}

/**
 * Top telemetry strip (Stitch header). Every readout is real: the open mission's target and
 * design revision, and the link margin from the backend analysis of the CURRENT revision only.
 * Nothing here is a clock, a callsign or a number the engine did not return.
 */
const subscribe = (cb: () => void) => {
  window.addEventListener(ACTIVE_MISSION_EVENT, cb);
  return () => window.removeEventListener(ACTIVE_MISSION_EVENT, cb);
};

export function TelemetryBar() {
  const open = useMissionStore((s) => s.mission);
  // run pages (control, debrief) do not open the design for editing: show the saved mission
  const activeId = useSyncExternalStore(subscribe, readActiveMission, () => null);
  const saved = useMemo(() => {
    if (open || !activeId) return null;
    const r = loadMission(activeId);
    return r.ok ? r.value : null;
  }, [open, activeId]);
  const mission = open ?? saved;
  const analysis = useMissionStore((s) => s.analysis);
  const analysisRevision = useMissionStore((s) => s.analysisRevision);
  const designRevision = useMissionStore((s) => s.designRevision);
  if (!mission) {
    return <span className="label-caps text-muted">No active mission · choose a scenario</span>;
  }
  const current = open !== null && analysis !== null && analysisRevision === designRevision;
  const link = current ? analysis.constraints.find((c) => c.id === "link-margin") : undefined;
  const linkText =
    link?.actual && link.actual.provenance.fidelity !== "not-modelled" ? formatQuantity(link.actual) : current ? "not modelled" : "—";
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-x-5 gap-y-1">
      <div className="flex min-w-0 items-center gap-2 bg-surface px-2 py-1">
        <span className="label-caps text-muted">Target</span>
        <span className="truncate font-mono text-sm font-semibold" data-testid="telemetry-target">
          {mission.destination.name}
        </span>
      </div>
      <Readout label="Design rev" value={String(open ? designRevision : mission.designRevision)} />
      <Readout label="Link margin" value={linkText} testId="telemetry-link" />
      {open ? <ReadinessSummary testId="telemetry-readiness" /> : <span className="label-caps text-muted" title="Open the architect to analyse this design">Saved design</span>}
    </div>
  );
}

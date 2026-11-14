"use client";

import Link from "next/link";

import { ExperimentalBadge } from "@/components/common/ExperimentalBadge";
import { isImportedRun, type RunData } from "@/lib/persistence/run-cache";
import { authorityAt, flownContacts } from "./authority";
import { AuthorityBanner } from "./AuthorityBanner";
import { AutonomyLog } from "./AutonomyLog";
import { DecisionCard } from "./DecisionCard";
import { ImportedDecisionNotice } from "./ImportedDecisionNotice";
import { EventLog } from "./EventLog";
import { PhaseRibbon } from "./PhaseRibbon";
import { PlaybackControls } from "./PlaybackControls";
import { currentPhase, linkMarginLimit, visibleEvents } from "./playback";
import { SchematicPanel } from "./SchematicPanel";
import { TelemetryCards, TelemetryCharts } from "./TelemetryPanel";
import { TelemetryResidual } from "./TelemetryResidual";
import { usePlayback } from "./usePlayback";

/** Mission control screen: plays back an immutable run. Nothing here computes mission results. */
export function MissionControl({ data, startDay }: { data: RunData; startDay: number }) {
  const run = data.run;
  const pb = usePlayback(run, startDay);
  const phase = currentPhase(run, pb.day);
  const shown = visibleEvents(pb.events, pb.day);
  const linkLimit = linkMarginLimit(data.analysis);
  const contacts = flownContacts(run);
  const policy = run.autonomyLog?.[0]?.policy ?? null;

  return (
    <div data-testid="mission-control" className="space-y-4">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Mission control</h1>
        <p className="break-all font-mono text-xs text-muted">Run {run.runId} · seed {run.seed}</p>
        {run.experimental ? <ExperimentalBadge /> : null}
        <Link
          data-testid="open-review"
          href={`/review/${run.runId}`}
          className="inline-flex min-h-11 items-center rounded-lg border border-accent-cyan/60 px-4 text-sm font-medium text-accent-cyan hover:bg-accent-cyan/10"
        >
          Open mission review
        </Link>
      </header>
      <PhaseRibbon run={run} day={pb.day} duration={pb.duration} />
      <AuthorityBanner contacts={contacts} day={pb.day} policy={policy} />
      <PlaybackControls pb={pb} />
      {pb.pending && isImportedRun(data) ? <ImportedDecisionNotice key={pb.pending.id} data={data} event={pb.pending} /> : null}
      {pb.pending && !isImportedRun(data) ? <DecisionCard
          key={pb.pending.id}
          event={pb.pending}
          runId={run.runId}
          telemetry={run.telemetry}
          linkLimit={linkLimit}
          authority={authorityAt(contacts, pb.pending.missionDay)}
        /> : null}
      <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <div className="min-w-0 space-y-4">
          <SchematicPanel phase={phase} day={pb.day} />
          <TelemetryCards samples={run.telemetry} day={pb.day} linkLimit={linkLimit} />
        </div>
        <EventLog events={shown} decisions={run.decisions} />
      </div>
      <section aria-label="Telemetry charts" className="space-y-2">
        <h2 className="text-base font-semibold">Telemetry history</h2>
        <TelemetryCharts samples={run.telemetry} day={pb.day} duration={pb.duration} linkLimit={linkLimit} />
      </section>
      <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <div className="min-w-0">
          <AutonomyLog run={run} day={pb.day} />
        </div>
        <div className="min-w-0">
          <TelemetryResidual run={run} day={pb.day} />
        </div>
      </div>
    </div>
  );
}

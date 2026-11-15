"use client";

import Link from "next/link";
import { useEffect } from "react";

import { writeActiveMission } from "@/lib/persistence/active-mission";

import { ExperimentalBadge } from "@/components/common/ExperimentalBadge";
import { isImportedRun, type RunData } from "@/lib/persistence/run-cache";
import { ConceptCard } from "@/components/learning/ConceptCard";
import { RunStageBar } from "@/components/progress/RunStageBar";
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
  useEffect(() => writeActiveMission(run.missionId), [run.missionId]);

  return (
    <div data-testid="mission-control" className="space-y-4">
      <header className="panel relative flex flex-wrap items-end justify-between gap-4 overflow-hidden p-5">
        <div aria-hidden className="pointer-events-none absolute inset-x-0 bottom-0 h-24 bg-[url('/backdrops/signal-waves.svg')] bg-cover bg-no-repeat" />
        <div aria-hidden className="scan-line pointer-events-none absolute inset-x-0 top-0 h-full bg-gradient-to-b from-accent-cyan/0 via-accent-cyan/5 to-accent-cyan/0" />
        <div className="min-w-0 space-y-1">
          <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-accent-amber">Mission operations</p>
          <h1 className="text-3xl font-semibold tracking-tight">Mission control</h1>
          <p className="break-all font-mono text-xs text-muted">Run {run.runId} · seed {run.seed} · design revision {run.designRevision}</p>
          {run.experimental ? <ExperimentalBadge /> : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href={`/architect/${run.missionId}`}
            className="inline-flex min-h-11 items-center rounded-lg border border-border px-4 text-sm text-muted hover:text-foreground"
          >
            Revise in architect
          </Link>
          <Link
            data-testid="open-review"
            href={`/review/${run.runId}`}
            className="inline-flex min-h-11 items-center rounded-lg border border-accent-cyan/60 bg-accent-cyan/10 px-4 text-sm font-medium text-accent-cyan hover:bg-accent-cyan/20"
          >
            Open mission review
          </Link>
        </div>
      </header>
      <RunStageBar missionId={run.missionId} view="control" />
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
      {/* operations room: the scene and its history on the left, the live telemetry bus,
          event log and health monitor on the right (Stitch mission-control layout) */}
      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="min-w-0 space-y-4">
          <SchematicPanel run={run} phase={phase} day={pb.day} />
          <section aria-label="Telemetry charts" className="panel space-y-2 p-3">
            <h2 className="font-mono text-xs uppercase tracking-[0.2em] text-primary">Telemetry history</h2>
            <TelemetryCharts samples={run.telemetry} day={pb.day} duration={pb.duration} linkLimit={linkLimit} />
          </section>
          <div className="panel space-y-4 p-3">
            <ConceptCard id="lo7" />
            <AutonomyLog run={run} day={pb.day} />
          </div>
        </div>
        <div className="min-w-0 space-y-4">
          <section aria-label="Telemetry bus" className="panel space-y-2 p-3">
            <h2 className="font-mono text-xs uppercase tracking-[0.2em] text-primary">Telemetry bus</h2>
            <TelemetryCards samples={run.telemetry} day={pb.day} linkLimit={linkLimit} />
          </section>
          <div className="panel p-3">
            <EventLog events={shown} decisions={run.decisions} />
          </div>
          <div className="panel p-3">
            <TelemetryResidual run={run} day={pb.day} />
          </div>
        </div>
      </div>
    </div>
  );
}

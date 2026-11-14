import { currentPhase, PHASE_LABEL, type MissionRun, type Phase } from "./playback";

/** Phase ribbon, elapsed mission day and spacecraft mode. Mode follows the phase (no separate model). */
export function PhaseRibbon({ run, day, duration }: { run: MissionRun; day: number; duration: number }) {
  const phases: Phase[] = [...run.phases];
  if (run.finalReport.outcome === "terminated" && !phases.includes("terminated")) phases.push("terminated");
  const current = currentPhase(run, day);
  const startOf = (p: Phase) => run.phaseTransitions.find((t) => t.phase === p)?.missionDay ?? null;
  return (
    <section aria-label="Mission phases" className="space-y-3 rounded-lg border border-border bg-surface p-3">
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
        <p data-testid="elapsed-day" className="text-lg font-semibold tabular-nums">
          Mission day {day.toFixed(1)} <span className="text-sm font-normal text-muted">of {duration.toFixed(1)} d</span>
        </p>
        <p data-testid="spacecraft-mode" className="text-sm">
          <span className="text-muted">Spacecraft mode: </span>
          <span className="font-medium">{current ? PHASE_LABEL[current] : "Not started"}</span>
          <span className="text-muted"> (follows the mission phase)</span>
        </p>
      </div>
      <ol data-testid="phase-ribbon" className="flex flex-wrap gap-2">
        {phases.map((p) => {
          const start = startOf(p);
          const state = p === current ? "current" : start !== null && start <= day ? "done" : "upcoming";
          return (
            <li
              key={p}
              data-testid={`phase-${p}`}
              data-state={state}
              aria-current={state === "current" ? "step" : undefined}
              className={`rounded-md border px-2.5 py-1 text-xs ${
                state === "current"
                  ? "border-accent-cyan bg-accent-cyan/10 font-semibold text-accent-cyan"
                  : state === "done"
                    ? "border-border text-foreground"
                    : "border-dashed border-border text-muted"
              }`}
            >
              {PHASE_LABEL[p]}
              <span className="sr-only"> ({state})</span>
              {start !== null ? <span className="ml-1 text-muted tabular-nums">d{Math.round(start)}</span> : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

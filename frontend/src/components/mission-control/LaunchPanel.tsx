"use client";

import { Rocket, ShieldAlert, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { apiPost } from "@/lib/api-client";
import { LaunchSequence } from "./LaunchSequence";
import { useMissionStore } from "@/state/mission-store";
import { useRunStore } from "@/state/run-store";

/** A refused launch or a launch error, tied to the design revision it was produced for. */
type Outcome =
  | { kind: "blocked"; revision: number; ids: string[]; message: string }
  | { kind: "error"; revision: number; message: string };

/**
 * Launch action (architect, readiness review). The seed comes from MissionState.randomSeed; the
 * backend decides whether the design may launch (hard constraints) and runs the simulation.
 *
 * A refusal belongs to the revision that was refused: as soon as the player edits the design
 * (a new revision), the old "blocked" result and its experimental-launch offer disappear, so a
 * fixed design can never be flown as an "experimental" run by mistake.
 */
export function LaunchPanel() {
  const router = useRouter();
  const mission = useMissionStore((s) => s.mission);
  const analysis = useMissionStore((s) => s.analysis);
  const analysisRevision = useMissionStore((s) => s.analysisRevision);
  const status = useMissionStore((s) => s.status);
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const launchRef = useRef<HTMLButtonElement>(null);

  // Arriving at #launch (stage rail "Mission control" / "Review" before any flight), on load or
  // from a link on this same page: bring the launch control into view and focus it.
  useEffect(() => {
    const go = () => {
      if (window.location.hash !== "#launch") return;
      launchRef.current?.closest("section")?.scrollIntoView({ block: "center" });
      launchRef.current?.focus({ preventScroll: true });
    };
    go();
    window.addEventListener("hashchange", go);
    return () => window.removeEventListener("hashchange", go);
  }, []);

  if (!mission) return null;
  const revision = mission.designRevision;
  // only a result for THIS revision is shown; an edit makes it obsolete
  const current = outcome && outcome.revision === revision ? outcome : null;
  const blocked = current?.kind === "blocked" ? current : null;
  const error = current?.kind === "error" ? current.message : null;

  async function launch(experimental: boolean) {
    if (!mission || busy) return;
    const launched = mission;
    setBusy(true);
    setOutcome(null);
    const res = await apiPost("/api/mission/simulate", {
      missionState: launched,
      randomSeed: launched.randomSeed,
      experimental,
    });
    if (res.ok && res.data) {
      useRunStore.getState().putRun(res.data);
      router.push(`/control/${res.data.run.runId}`);
      return;
    }
    setBusy(false);
    if (res.error?.code === "LAUNCH_BLOCKED") {
      const ids = res.error.details?.["failingConstraintIds"];
      setOutcome({
        kind: "blocked",
        revision: launched.designRevision,
        ids: Array.isArray(ids) ? ids.map(String) : [],
        message: res.error.message,
      });
      return;
    }
    setOutcome({ kind: "error", revision: launched.designRevision, message: res.error?.message ?? "The mission could not be launched." });
  }

  const labelOf = (id: string) => analysis?.constraints.find((c) => c.id === id)?.label ?? id;

  // Pre-launch status from the engine's analysis of this exact revision (never a guess).
  const analysed = analysis !== null && analysisRevision === revision;
  const hardFails = analysed ? analysis.constraints.filter((c) => c.status === "fail") : [];
  const watches = analysed ? analysis.constraints.filter((c) => c.status === "warning") : [];
  const preflight = !analysed ? (
    <span data-testid="launch-preflight" data-state="pending" className="inline-flex items-center gap-1.5 text-xs text-muted">
      {status === "calculating" ? "Engine is analysing this revision…" : "Not analysed yet; the engine checks the design when you launch."}
    </span>
  ) : hardFails.length === 0 ? (
    <span data-testid="launch-preflight" data-state="ready" className="inline-flex items-center gap-1.5 text-xs text-primary">
      <ShieldCheck aria-hidden className="h-3.5 w-3.5" /> No hard constraint fails at revision {revision}.
      {watches.length ? (
        <span className="text-accent-amber">
          {" "}
          {watches.length} watch item{watches.length > 1 ? "s" : ""} ({watches.map((c) => c.label).join(", ")}) keep it from
          mission-ready; launch is allowed.
        </span>
      ) : (
        " Mission-ready."
      )}
    </span>
  ) : (
    <span data-testid="launch-preflight" data-state="blocked" className="inline-flex items-center gap-1.5 text-xs text-accent-amber">
      <ShieldAlert aria-hidden className="h-3.5 w-3.5" /> {hardFails.length} hard constraint{hardFails.length > 1 ? "s" : ""} failing (
      {hardFails.map((c) => c.label).join(", ")}): the engine will refuse a normal launch.
    </span>
  );

  return (
    <section id="launch" aria-label="Launch" className="panel scroll-mt-24 space-y-3 p-3">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          ref={launchRef}
          data-testid="launch-button"
          onClick={() => launch(false)}
          disabled={busy}
          className="inline-flex min-h-11 items-center gap-2 border border-accent-cyan/60 bg-accent-cyan/10 px-4 text-sm font-medium text-accent-cyan hover:bg-accent-cyan/20 disabled:opacity-50"
        >
          <Rocket aria-hidden className="h-4 w-4" />
          {busy ? "Launching…" : "Launch mission"}
        </button>
        {busy ? (
          <LaunchSequence />
        ) : (
          <div className="flex min-w-0 flex-col gap-0.5">
            <p className="text-xs text-muted">
              Runs one deterministic simulation of revision {revision} with seed {mission.randomSeed}.
            </p>
            {preflight}
          </div>
        )}
      </div>
      {blocked ? (
        <div data-testid="launch-blocked" role="alert" className="space-y-2 border border-accent-amber/60 p-3 text-sm">
          <p className="font-medium">{blocked.message}</p>
          <p className="text-xs text-muted">Refused for design revision {blocked.revision}. Editing the design clears this.</p>
          <ul className="list-disc space-y-1 pl-5">
            {blocked.ids.map((id) => (
              <li key={id} data-testid={`launch-blocked-constraint-${id}`}>
                {labelOf(id)} <span className="font-mono text-xs text-muted">({id})</span>
              </li>
            ))}
          </ul>
          <button
            type="button"
            data-testid="launch-experimental"
            onClick={() => launch(true)}
            disabled={busy}
            className="inline-flex min-h-11 items-center border border-accent-amber/60 px-4 text-sm font-medium text-accent-amber hover:bg-accent-amber/10 disabled:opacity-50"
          >
            Launch in experimental mode
          </button>
          <p className="text-xs text-muted">The run will be badged: Experimental run — design violates hard limits.</p>
        </div>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm text-accent-red">
          {error}
        </p>
      ) : null}
    </section>
  );
}

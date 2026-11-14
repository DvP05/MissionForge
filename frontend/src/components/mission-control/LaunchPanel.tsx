"use client";

import { Rocket } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { apiPost } from "@/lib/api-client";
import { useMissionStore } from "@/state/mission-store";
import { useRunStore } from "@/state/run-store";

type Blocked = { ids: string[]; message: string };

/**
 * Launch action for the Architect. The seed comes from MissionState.randomSeed; the
 * backend decides whether the design may launch (hard constraints) and runs the simulation.
 */
export function LaunchPanel() {
  const router = useRouter();
  const mission = useMissionStore((s) => s.mission);
  const analysis = useMissionStore((s) => s.analysis);
  const [busy, setBusy] = useState(false);
  const [blocked, setBlocked] = useState<Blocked | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!mission) return null;

  async function launch(experimental: boolean) {
    if (!mission || busy) return;
    setBusy(true);
    setError(null);
    const res = await apiPost("/api/mission/simulate", {
      missionState: mission,
      randomSeed: mission.randomSeed,
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
      setBlocked({ ids: Array.isArray(ids) ? ids.map(String) : [], message: res.error.message });
      return;
    }
    setBlocked(null);
    setError(res.error?.message ?? "The mission could not be launched.");
  }

  const labelOf = (id: string) => analysis?.constraints.find((c) => c.id === id)?.label ?? id;

  return (
    <section aria-label="Launch" className="space-y-3 rounded-lg border border-border bg-surface p-3">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          data-testid="launch-button"
          onClick={() => launch(false)}
          disabled={busy}
          className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-accent-cyan/60 bg-accent-cyan/10 px-4 text-sm font-medium text-accent-cyan hover:bg-accent-cyan/20 disabled:opacity-50"
        >
          <Rocket aria-hidden className="h-4 w-4" />
          {busy ? "Launching…" : "Launch mission"}
        </button>
        <p className="text-xs text-muted">Runs one deterministic simulation with seed {mission.randomSeed}.</p>
      </div>
      {blocked ? (
        <div data-testid="launch-blocked" role="alert" className="space-y-2 rounded-lg border border-accent-amber/60 p-3 text-sm">
          <p className="font-medium">{blocked.message}</p>
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
            className="inline-flex min-h-11 items-center rounded-lg border border-accent-amber/60 px-4 text-sm font-medium text-accent-amber hover:bg-accent-amber/10 disabled:opacity-50"
          >
            Launch in experimental mode
          </button>
          <p className="text-xs text-muted">The run will be badged: Experimental run — design violates hard limits.</p>
        </div>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm text-red-300">
          {error}
        </p>
      ) : null}
    </section>
  );
}

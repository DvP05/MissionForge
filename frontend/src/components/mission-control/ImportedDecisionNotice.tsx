"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { apiPost } from "@/lib/api-client";
import { notifyStorageChanged } from "@/lib/persistence/events";
import { clearReplayRecord } from "@/lib/persistence/replay";
import type { RunData } from "@/lib/persistence/run-cache";
import { useRunStore } from "@/state/run-store";
import type { MissionEvent } from "./playback";

/**
 * Imported runs are not held by the server, so a decision cannot branch them. Instead the player
 * can re-simulate: the run's own snapshot, seed, event set and recorded player decisions are sent
 * to POST /api/mission/simulate, and playback continues on the new (server-held) run.
 */
export function ImportedDecisionNotice({ data, event }: { data: RunData; event: MissionEvent }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = data.run;

  async function resimulate() {
    setBusy(true);
    setError(null);
    const decisions: Record<string, string> = {};
    for (const d of run.decisions) if (d.decisionMaker === "player") decisions[d.eventId] = d.choiceId;
    const res = await apiPost("/api/mission/simulate", {
      missionState: run.inputSnapshot,
      randomSeed: run.seed,
      scenarioEventSetId: run.scenarioEventSetId,
      experimental: run.experimental,
      decisions: Object.keys(decisions).length ? decisions : null,
    });
    if (res.ok && res.data) {
      useRunStore.getState().putRun(res.data);
      clearReplayRecord(res.data.run.runId); // the import-time status described the imported copy
      notifyStorageChanged();
      router.push(`/control/${res.data.run.runId}?day=${event.missionDay}`);
      return;
    }
    setBusy(false);
    setError(res.error?.message ?? "The run could not be re-simulated.");
  }

  return (
    <section data-testid="imported-decision-notice" className="space-y-3 rounded-lg border border-accent-amber/60 bg-accent-amber/5 p-4">
      <p role="alert" className="text-xs font-medium uppercase tracking-wide text-accent-amber">
        Decision point — day {event.missionDay.toFixed(1)} — playback paused
      </p>
      <h2 className="text-lg font-semibold">{event.title}</h2>
      <p className="text-sm">
        This run was imported &mdash; re-simulate to make decisions. Imported runs are shown as recorded and cannot be branched.
        Re-simulating runs the same design, seed and your earlier choices on this server and opens the new run here.
      </p>
      {error ? (
        <p role="alert" className="text-sm text-accent-red">
          {error}
        </p>
      ) : null}
      <button
        type="button"
        data-testid="resimulate-run"
        disabled={busy}
        onClick={resimulate}
        className="inline-flex min-h-11 items-center rounded-lg border border-accent-cyan/60 px-4 text-sm font-medium text-accent-cyan hover:bg-accent-cyan/10 disabled:opacity-50"
      >
        {busy ? "Re-simulating\u2026" : "Re-simulate"}
      </button>
    </section>
  );
}

"use client";

import { useBackendHealth } from "@/components/shell/BackendHealth";
import { clientMismatches, describeMismatches, loadReplayRecord } from "@/lib/persistence/replay";
import type { RunData } from "@/lib/persistence/run-cache";

/** Shown on a run page when the run cannot be replayed identically here (never claims identity). */
export function ReplayBanner({ data }: { data: RunData }) {
  const { state } = useBackendHealth();
  const record = loadReplayRecord(data.run.runId);
  let reason: string | null = null;
  if (record && record.status !== "identical-replay") {
    reason = record.mismatches.length ? describeMismatches(record.mismatches) : "the re-run differed";
  } else if (!record && state.kind === "online") {
    const hint = clientMismatches(data.run, {
      engineVersion: state.health.engineVersion,
      catalogVersion: state.health.catalogVersion,
      schemaVersion: state.health.schemaVersion,
    });
    if (hint.length) reason = describeMismatches(hint);
  }
  if (!reason) return null;
  return (
    <p data-testid="run-version-banner" role="status" className="mb-4 rounded-lg border border-accent-amber/60 p-3 text-sm">
      Version mismatch &mdash; not an identical replay: {reason}. This run is shown as recorded; re-running it here would give a
      different result.
    </p>
  );
}

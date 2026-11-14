"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useBackendHealth } from "@/components/shell/BackendHealth";
import { useImportNotice } from "@/state/import-notice-store";
import { StatusPill } from "@/components/common/StatusPill";
import { STORAGE_CHANGED_EVENT, notifyStorageChanged } from "@/lib/persistence/events";
import {
  clientMismatches,
  describeMismatches,
  loadReplayRecord,
  replayRun,
  statusLabel,
  type ReplayRecord,
} from "@/lib/persistence/replay";
import { listCachedRuns, type RunData } from "@/lib/persistence/run-cache";

type Check = { state: "running" } | { state: "failed"; message: string } | { state: "done"; summary: string };

/**
 * Saved runs of this mission with their replay status. "Identical replay" is shown only after an explicit
 * replay (POST /api/mission/replay) returned identical=true. An import only says "versions match";
 * a version difference is always shown as "not an identical replay".
 */
export function RunsPanel({ missionId }: { missionId: string }) {
  const { state: health } = useBackendHealth();
  const [runs, setRuns] = useState<RunData[]>([]);
  const [records, setRecords] = useState<Record<string, ReplayRecord | null>>({});
  const [checks, setChecks] = useState<Record<string, Check>>({});

  useEffect(() => {
    const read = () => {
      const list = listCachedRuns(missionId);
      setRuns(list);
      setRecords(Object.fromEntries(list.map((r) => [r.run.runId, loadReplayRecord(r.run.runId)])));
    };
    read();
    window.addEventListener(STORAGE_CHANGED_EVENT, read);
    return () => window.removeEventListener(STORAGE_CHANGED_EVENT, read);
  }, [missionId]);

  const notice = useImportNotice((s) => s.notice);
  const shownNotice = notice && notice.missionId === missionId ? notice : null;

  if (runs.length === 0 && !shownNotice) return null;

  const current =
    health.kind === "online"
      ? {
          engineVersion: health.health.engineVersion,
          catalogVersion: health.health.catalogVersion,
          schemaVersion: health.health.schemaVersion,
        }
      : null;

  const mismatchBanner = runs.find((r) => {
    const rec = records[r.run.runId];
    if (rec) return rec.status === "version-mismatch" || rec.status === "diverged";
    return current !== null && clientMismatches(r.run, current).length > 0;
  });

  const verify = async (data: RunData) => {
    const id = data.run.runId;
    setChecks((c) => ({ ...c, [id]: { state: "running" } }));
    const res = await replayRun(data.run);
    if (!res.ok) {
      setChecks((c) => ({ ...c, [id]: { state: "failed", message: res.message } }));
      return;
    }
    const summary =
      res.status === "identical-replay" && res.run
        ? `Identical replay: re-running reproduced all ${res.run.events.length} events, ${res.run.telemetry.length} telemetry samples and ${res.run.decisions.length} decisions exactly.`
        : statusLabel(res.status, res.mismatches);
    setChecks((c) => ({ ...c, [id]: { state: "done", summary } }));
    notifyStorageChanged();
  };

  return (
    <section data-testid="runs-panel" aria-labelledby="runs-heading" className="space-y-3 rounded-xl border border-border bg-surface p-4">
      <h2 id="runs-heading" className="text-base font-semibold">
        Saved runs
      </h2>
      {shownNotice ? (
        <p data-testid="import-notice" role="alert" className="rounded-lg border border-accent-amber/60 p-3 text-sm">
          {shownNotice.notKept.length} of {shownNotice.total} imported runs could not be kept in this browser (it keeps at most
          6 runs, or storage was full): {shownNotice.notKept.join(", ")}. Your other saved runs were not touched.
        </p>
      ) : null}
      {mismatchBanner ? (
        <p data-testid="replay-mismatch-banner" role="alert" className="rounded-lg border border-accent-amber/60 p-3 text-sm">
          Version mismatch &mdash; not an identical replay. At least one saved run was made with different versions than this
          server uses, so it can be viewed but cannot be re-run to the same result.
        </p>
      ) : null}
      <ul className="space-y-3">
        {runs.map((data) => {
          const id = data.run.runId;
          const rec = records[id];
          const hint = current ? clientMismatches(data.run, current) : [];
          const check = checks[id];
          return (
            <li key={id} data-testid={`run-row-${id}`} className="space-y-1 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="break-all font-mono text-xs">{id}</span>
                <StatusPill>Revision {data.run.designRevision}</StatusPill>
                <StatusPill>Seed {data.run.seed}</StatusPill>
                <StatusPill>{data.finalReport.outcome}</StatusPill>
                <Link href={`/control/${id}`} className="text-accent-cyan underline-offset-2 hover:underline">
                  Open
                </Link>
                <button
                  type="button"
                  data-testid={`run-verify-${id}`}
                  disabled={check?.state === "running"}
                  onClick={() => verify(data)}
                  className="inline-flex min-h-11 items-center rounded-lg border border-border px-3 hover:text-accent-cyan disabled:opacity-50"
                >
                  {check?.state === "running" ? "Replaying…" : "Verify replay"}
                </button>
              </div>
              <p data-testid={`run-status-${id}`} className="text-muted">
                {rec
                  ? statusLabel(rec.status, rec.mismatches)
                  : hint.length > 0
                    ? `Version mismatch — not an identical replay: ${describeMismatches(hint)}`
                    : "Replay status not checked yet. Use Verify replay."}
              </p>
              {check?.state === "done" ? (
                <p data-testid={`run-replay-result-${id}`} role="status">
                  {check.summary}
                </p>
              ) : null}
              {check?.state === "failed" ? (
                <p role="alert" className="text-accent-amber">
                  {check.message}
                </p>
              ) : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

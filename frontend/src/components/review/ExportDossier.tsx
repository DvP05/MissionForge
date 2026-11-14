"use client";

import { useState } from "react";

import { apiPost } from "@/lib/api-client";
import { downloadBlob } from "@/lib/persistence/package";
import type { RunData } from "@/lib/persistence/run-cache";

type Done = { evidence: number; replay: string; files: string[] };

/**
 * Evidence Passport export (architecture 19.9). The server re-validates the run, rebuilds the
 * budgets and re-checks the replay; the browser only saves the two files it gets back.
 */
export function ExportDossier({ data }: { data: RunData }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<Done | null>(null);
  const runId = data.run.runId;

  async function onExport() {
    setBusy(true);
    setError(null);
    setDone(null);
    const res = await apiPost("/api/mission/dossier", { run: data.run }, { timeoutMs: 30_000 });
    setBusy(false);
    if (!res.ok || !res.data) {
      setError(`${res.error?.message ?? "The passport could not be created."} Nothing was downloaded.`);
      return;
    }
    const jsonName = `missionforge-passport-${runId}.json`;
    const htmlName = `missionforge-passport-${runId}.html`;
    downloadBlob(new Blob([JSON.stringify(res.data.package, null, 2)], { type: "application/json" }), jsonName);
    downloadBlob(new Blob([res.data.html], { type: "text/html" }), htmlName);
    setDone({
      evidence: res.data.package.evidence?.length ?? 0,
      replay: /identical replay\)/i.test(res.data.html) ? "verified identical on the server" : "not verified as identical",
      files: [jsonName, htmlName],
    });
  }

  return (
    <section data-testid="export-dossier" aria-labelledby="export-dossier-h" className="space-y-2">
      <h2 id="export-dossier-h" className="text-lg font-semibold">
        Evidence Passport
      </h2>
      <p className="text-sm text-muted">
        A JSON package that re-imports, plus a printable HTML report: manifest, sources and assumptions, limitations. Independent educational prototype; not a NASA/JPL product or endorsement.
      </p>
      <button
        type="button"
        data-testid="export-passport"
        disabled={busy}
        onClick={onExport}
        className="inline-flex min-h-11 items-center rounded-lg border border-border px-4 text-sm hover:text-accent-cyan disabled:opacity-60"
      >
        {busy ? "Exporting..." : "Export Evidence Passport"}
      </button>
      {error ? (
        <p role="alert" data-testid="export-passport-error" className="text-sm text-red-400">
          {error}
        </p>
      ) : null}
      {done ? (
        <div role="status" data-testid="export-passport-done" className="rounded-lg border border-border p-3 text-sm">
          <p>Downloaded {done.files.join(" and ")}.</p>
          <ul className="list-disc pl-5">
            <li>Run manifest (versions, event set, seed) and the full run</li>
            <li>{done.evidence} evidence records, each with a source link or an explicit unavailable-source label</li>
            <li>Replay check: {done.replay}</li>
            <li>Limitations and the non-endorsement statement</li>
          </ul>
        </div>
      ) : null}
    </section>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import {
  applyImport,
  downloadBlob,
  exportPackage,
  packageFileName,
  prepareImport,
  type ImportFailure,
  type PreparedImport,
} from "@/lib/persistence/package";
import { notifyStorageChanged } from "@/lib/persistence/events";
import { useImportNotice } from "@/state/import-notice-store";
import { useMissionStore } from "@/state/mission-store";

const BTN =
  "inline-flex min-h-11 items-center rounded-lg border border-border px-3 text-sm hover:text-accent-cyan disabled:cursor-not-allowed disabled:opacity-50";

/** Export the open mission as a versioned package. `testId` lets the quota prompt reuse it. */
export function ExportButton({ testId = "export-package", label = "Export package" }: { testId?: string; label?: string }) {
  const mission = useMissionStore((s) => s.mission);
  const analysis = useMissionStore((s) => s.analysis);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!mission) return null;
  return (
    <>
      <button
        type="button"
        data-testid={testId}
        disabled={busy}
        className={BTN}
        onClick={async () => {
          setBusy(true);
          setError(null);
          try {
            downloadBlob(await exportPackage(mission, analysis), packageFileName(mission));
          } catch {
            setError("The package could not be created.");
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "Exporting…" : label}
      </button>
      {error ? (
        <span role="alert" className="text-sm text-accent-amber">
          {error}
        </span>
      ) : null}
    </>
  );
}

type Panel =
  | { kind: "error"; failure: ImportFailure }
  | { kind: "conflict"; prepared: PreparedImport }
  | { kind: "busy" }
  | null;

/**
 * File picker for a mission package. The file always goes through POST /api/mission/import; the
 * saved mission and the open workspace change only after the server accepts it (and, when a
 * different local copy of the same mission exists, after the player agrees to replace it).
 */
export function ImportButton() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [panel, setPanel] = useState<Panel>(null);

  const finish = (prepared: PreparedImport) => {
    const applied = applyImport(prepared);
    if (!applied.ok) {
      setPanel({ kind: "error", failure: applied });
      return;
    }
    // Drop any in-memory copy, reload from the freshly written storage, then open it.
    const store = useMissionStore.getState();
    store.reset();
    store.hydrate(applied.missionId);
    notifyStorageChanged();
    useImportNotice.getState().setNotice(
      applied.notKept.length ? { missionId: applied.missionId, total: applied.runs.length, notKept: applied.notKept } : null,
    );
    setPanel(null);
    router.push(`/mission/${applied.missionId}`);
  };

  return (
    <div className="space-y-2">
      <input
        ref={inputRef}
        type="file"
        accept="application/json,.json"
        data-testid="import-package-input"
        className="hidden"
        onChange={async (e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (!file) return;
          setPanel({ kind: "busy" });
          const prepared = await prepareImport(file);
          if (!prepared.ok) setPanel({ kind: "error", failure: prepared });
          else if (prepared.conflict) setPanel({ kind: "conflict", prepared });
          else finish(prepared);
        }}
      />
      <button
        type="button"
        data-testid="import-package"
        className={BTN}
        disabled={panel?.kind === "busy"}
        onClick={() => inputRef.current?.click()}
      >
        {panel?.kind === "busy" ? "Checking file…" : "Import package"}
      </button>
      {panel?.kind === "error" ? (
        <div data-testid="import-error" role="alert" className="max-w-xl space-y-2 rounded-lg border border-accent-amber/60 p-3 text-sm">
          <p className="font-medium">Import failed</p>
          <p data-testid="import-error-message">{panel.failure.message}</p>
          {panel.failure.details?.length ? (
            <ul className="list-disc pl-5 text-muted">
              {panel.failure.details.map((d) => (
                <li key={d}>{d}</li>
              ))}
            </ul>
          ) : null}
          <button type="button" className={BTN} onClick={() => setPanel(null)}>
            Dismiss
          </button>
        </div>
      ) : null}
      {panel?.kind === "conflict" ? (
        <div data-testid="import-conflict" role="alertdialog" aria-label="Replace saved mission" className="max-w-xl space-y-2 rounded-lg border border-accent-amber/60 p-3 text-sm">
          <p>
            A different saved copy of this mission already exists in this browser (&ldquo;{panel.prepared.conflict?.title}&rdquo;, revision{" "}
            {panel.prepared.conflict?.revision}). Replace it with the imported revision {panel.prepared.data.package.mission.designRevision}?
          </p>
          <div className="flex flex-wrap gap-2">
            <button type="button" data-testid="import-conflict-replace" className={BTN} onClick={() => finish(panel.prepared)}>
              Replace saved mission
            </button>
            <button type="button" data-testid="import-conflict-cancel" className={BTN} onClick={() => setPanel(null)}>
              Keep my saved mission
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

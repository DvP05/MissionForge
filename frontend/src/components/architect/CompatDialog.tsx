"use client";

import { useEffect, useRef } from "react";

import { formatSigned } from "@/lib/format";
import { type CatalogComponent, type CompatConflict } from "./catalog-helpers";
import { shortName } from "./OptionCard";

export interface PendingSwap {
  component: CatalogComponent;
  conflicts: CompatConflict[];
  delta: number | null;
}

/**
 * Confirmation before a swap that breaks a catalogue compatibility rule (prod 8.3).
 * Native modal dialog: focus is trapped, Escape cancels, focus returns to the trigger.
 */
export function CompatDialog({
  pending,
  nameOf,
  onCancel,
  onConfirm,
}: {
  pending: PendingSwap | null;
  nameOf: (id: string) => string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (pending && !dialog.open) dialog.showModal();
    return () => {
      if (dialog.open) dialog.close();
    };
  }, [pending]);

  if (!pending) return null;
  const affected = Array.from(new Set(pending.conflicts.map((c) => c.affectedId)));
  return (
    <dialog
      ref={ref}
      data-testid="compat-dialog"
      aria-labelledby="compat-title"
      onCancel={(event) => {
        event.preventDefault();
        onCancel();
      }}
      className="m-auto w-[min(32rem,calc(100vw-2rem))] rounded-xl border border-border bg-surface p-5 text-foreground backdrop:bg-black/60"
    >
      <h2 id="compat-title" className="text-lg font-semibold">
        Check compatibility before swapping
      </h2>
      <p className="mt-2 text-sm">
        Choosing {shortName(pending.component)} breaks a compatibility rule for:
      </p>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
        {affected.map((id) => (
          <li key={id} data-testid="compat-affected">
            {nameOf(id)}
          </li>
        ))}
      </ul>
      <ul className="mt-2 space-y-1 text-xs text-muted">
        {pending.conflicts.map((c) => (
          <li key={`${c.componentId}-${c.otherId}`}>{c.message}</li>
        ))}
      </ul>
      <p className="mt-3 text-sm">
        Nothing else will be changed. The backend will report a compatibility failure until you choose a
        compatible alternative.
      </p>
      {pending.delta !== null ? (
        <p className="mt-2 text-sm text-muted">
          Catalogue list cost delta ({pending.component.parameters.cost?.provenance.fidelity ?? "unlabelled"}): {formatSigned(pending.delta, "USD")}
        </p>
      ) : null}
      <div className="mt-4 flex flex-wrap justify-end gap-2">
        <button
          type="button"
          autoFocus
          onClick={onCancel}
          className="inline-flex min-h-11 items-center rounded-lg border border-border px-4 text-sm font-medium"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={onConfirm}
          className="inline-flex min-h-11 items-center rounded-lg border border-accent-amber/60 px-4 text-sm font-medium text-accent-amber hover:bg-accent-amber/10"
        >
          Swap anyway
        </button>
      </div>
    </dialog>
  );
}

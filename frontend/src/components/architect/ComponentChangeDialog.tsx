"use client";

import { ArrowRight, TriangleAlert } from "lucide-react";
import { useEffect, useRef } from "react";

import { FidelityBadge } from "@/components/common/FidelityBadge";
import { formatQuantity, formatSigned, humanize, MISSING } from "@/lib/format";
import { useChangeStore } from "@/state/change-store";
import { useMissionStore } from "@/state/mission-store";
import { applyChange, measurementsLost } from "./component-actions";
import {
  CATEGORY_ORDER,
  conflictsForCandidate,
  costDelta,
  KEY_PARAMETERS,
  selectedIds,
  type CatalogComponent,
} from "./catalog-helpers";
import { shortName } from "./OptionCard";

/**
 * Confirmation for a component change (design_update.md 6.3). Replace shows the installed and
 * the new component side by side; remove lists the measurements left without a capable
 * instrument; any catalogue rule conflict is named. Nothing else in the design is changed.
 * Native modal dialog: focus is trapped, Escape cancels, focus returns to the trigger.
 */
export function ComponentChangeDialog({ index }: { index: Map<string, CatalogComponent> }) {
  const pending = useChangeStore((s) => s.pending);
  const mission = useMissionStore((s) => s.mission);
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (pending && !dialog.open) {
      dialog.showModal();
      // focus the safe default once the modal is open (React autoFocus runs too early)
      dialog.querySelector<HTMLElement>("[data-autofocus='true']")?.focus();
    }
    return () => {
      if (dialog.open) dialog.close();
    };
  }, [pending]);

  if (!pending || !mission) return null;
  const component = index.get(pending.componentId);
  if (!component) return null;
  const meta = CATEGORY_ORDER.find((c) => c.category === pending.category)!;
  const current = pending.kind === "replace" ? index.get(selectedIds(mission, pending.category)[0]) : undefined;
  const conflicts =
    pending.kind === "remove" ? [] : conflictsForCandidate(index, mission, pending.category, pending.componentId);
  const lost = pending.kind === "remove" ? measurementsLost(mission, index, pending.componentId) : [];
  const delta = costDelta(index, mission, pending.category, component);
  const nameOf = (id: string) => (index.has(id) ? shortName(index.get(id)!) : id);
  const keys = KEY_PARAMETERS[pending.category];
  const destructive = conflicts.length > 0 || lost.length > 0;

  const close = () => {
    const opener = pending.opener;
    useChangeStore.getState().cancel();
    opener?.focus();
  };
  const confirm = () => {
    const opener = pending.opener;
    applyChange(pending.kind, pending.category, pending.componentId);
    opener?.focus();
  };

  const title =
    pending.kind === "replace"
      ? `Replace the ${meta.label.toLowerCase()}`
      : pending.kind === "remove"
        ? `Remove ${shortName(component)}`
        : `Add ${shortName(component)}`;
  const confirmLabel = conflicts.length > 0 ? "Swap anyway" : pending.kind === "replace" ? "Replace" : pending.kind === "remove" ? "Remove" : "Add";

  return (
    <dialog
      ref={ref}
      data-testid={conflicts.length > 0 ? "compat-dialog" : "change-dialog"}
      data-kind={pending.kind}
      aria-labelledby="change-title"
      onCancel={(event) => {
        event.preventDefault();
        close();
      }}
      className="m-auto w-[min(36rem,calc(100vw-2rem))] rounded-xl border border-border bg-surface p-5 text-foreground backdrop:bg-black/70"
    >
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-primary">{meta.label}</p>
      <h2 id="change-title" className="mt-1 text-lg font-semibold">
        {title}
      </h2>

      {pending.kind === "replace" && current ? (
        <div className="mt-3 overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-left text-sm" data-testid="change-compare">
            <caption className="sr-only">Installed component compared with the replacement</caption>
            <thead className="text-xs text-muted">
              <tr>
                <th scope="col" className="px-3 py-2 font-medium">Specification</th>
                <th scope="col" className="px-3 py-2 font-medium">Installed: {shortName(current)}</th>
                <th scope="col" className="px-3 py-2 font-medium">
                  <span className="inline-flex items-center gap-1">
                    <ArrowRight aria-hidden className="h-3.5 w-3.5" /> New: {shortName(component)}
                  </span>
                </th>
              </tr>
            </thead>
            <tbody className="readout">
              {keys.map((k) => (
                <tr key={k} className="border-t border-border/60">
                  <th scope="row" className="px-3 py-1.5 font-sans font-normal text-muted">{humanize(k)}</th>
                  <td className="px-3 py-1.5">{current.parameters[k] ? formatQuantity(current.parameters[k]) : MISSING}</td>
                  <td className="px-3 py-1.5 text-foreground">{component.parameters[k] ? formatQuantity(component.parameters[k]) : MISSING}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {pending.kind === "add" ? (
        <p className="mt-2 text-sm text-muted">
          Adds a payload slot with: {(component.capabilities ?? []).map(humanize).join(", ") || "no listed capability"}.
        </p>
      ) : null}

      {pending.kind === "remove" ? (
        lost.length > 0 ? (
          <div role="note" data-testid="change-lost" className="mt-3 rounded-lg border border-accent-red/50 bg-accent-red/10 p-3 text-sm">
            <p className="flex items-center gap-1.5 font-medium text-accent-red">
              <TriangleAlert aria-hidden className="h-4 w-4" /> Leaves required measurements without an instrument
            </p>
            <ul className="mt-1 list-disc space-y-0.5 pl-5">
              {lost.map(({ objective, measurement }) => (
                <li key={measurement.id}>
                  {measurement.description} <span className="text-muted">({objective.title})</span>
                </li>
              ))}
            </ul>
            <p className="mt-1 text-xs text-muted">From the catalogue capabilities; the engine re-checks coverage after the change.</p>
          </div>
        ) : (
          <p className="mt-2 text-sm text-muted">Every required measurement keeps at least one capable instrument (by catalogue capability).</p>
        )
      ) : null}

      {conflicts.length > 0 ? (
        <div className="mt-3 space-y-1 rounded-lg border border-accent-amber/50 bg-accent-amber/10 p-3 text-sm">
          <p className="font-medium text-accent-amber">Check compatibility before swapping. This breaks a rule for:</p>
          <ul className="list-disc space-y-0.5 pl-5">
            {Array.from(new Set(conflicts.map((c) => c.affectedId))).map((id) => (
              <li key={id} data-testid="compat-affected">{nameOf(id)}</li>
            ))}
          </ul>
          <ul className="space-y-0.5 text-xs text-muted">
            {conflicts.map((c) => (
              <li key={`${c.componentId}-${c.otherId}`}>{c.message}</li>
            ))}
          </ul>
          <p className="text-xs">The backend will report a compatibility failure until you choose a compatible alternative.</p>
        </div>
      ) : null}

      <p className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted">Catalogue list cost delta:</span>
        <span className="readout">{delta === null ? `${MISSING} no catalogue cost` : formatSigned(delta, "USD")}</span>
        {delta !== null && component.parameters.cost ? <FidelityBadge fidelity={component.parameters.cost.provenance.fidelity} /> : null}
      </p>
      <p className="mt-2 text-xs text-muted">
        Nothing else in the design changes. After you confirm, this becomes a new design revision and the engine
        re-analyses it; you can undo it from the impact report.
      </p>

      <div className="mt-4 flex flex-wrap justify-end gap-2">
        <button type="button" data-autofocus={destructive ? "true" : "false"} onClick={close} className="btn btn-tertiary">
          Cancel
        </button>
        <button
          type="button"
          data-autofocus={destructive ? "false" : "true"}
          data-testid="confirm-change"
          onClick={confirm}
          className={`btn ${pending.kind === "remove" || conflicts.length > 0 ? "btn-danger" : "btn-primary"}`}
        >
          {confirmLabel}
        </button>
      </div>
    </dialog>
  );
}

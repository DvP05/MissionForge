"use client";

import { CircleCheck, Eye, Minus, Plus, Repeat2, TriangleAlert } from "lucide-react";

import { FidelityBadge } from "@/components/common/FidelityBadge";
import { ProvenancePopover } from "@/components/common/ProvenancePopover";
import { formatQuantity, formatSigned, humanize, MISSING } from "@/lib/format";
import { useArchitectUi } from "@/state/architect-ui-store";
import { useChangeStore } from "@/state/change-store";
import type { ComponentCategory } from "@/state/mission-store";
import { KEY_PARAMETERS, type CatalogComponent, type CompatConflict } from "./catalog-helpers";

export function shortName(c: { name: string }): string {
  return c.name.replace(/^Archetype:\s*/, "");
}

/** Catalogue parameters to show: the category's key ones (at most four). */
function keyParameters(category: ComponentCategory, c: CatalogComponent): [string, CatalogComponent["parameters"][string]][] {
  const wanted = KEY_PARAMETERS[category].filter((k) => k in c.parameters && k !== "cost").slice(0, 3);
  const keys = wanted.length > 0 ? wanted : Object.keys(c.parameters).slice(0, 3);
  return keys.map((k) => [k, c.parameters[k]]);
}

/**
 * One catalogue option (design_update.md 6.2 / 6.4). Installed, inspected, incompatible and
 * awaiting-confirmation are separate, labelled states; the primary action names exactly
 * what will happen (Add / Replace / Remove), and Details only inspects.
 */
export function OptionCard({
  category,
  component,
  selected,
  multi,
  conflicts,
  delta,
  affectedName,
  onChoose,
}: {
  category: ComponentCategory;
  component: CatalogComponent;
  /** Installed in the current design. */
  selected: boolean;
  multi: boolean;
  conflicts: CompatConflict[];
  /** Catalogue list cost delta in USD, or null when not available. */
  delta: number | null;
  /** Resolves a conflicting component id to its display name. */
  affectedName: (id: string) => string;
  onChoose: (component: CatalogComponent, opener: HTMLElement) => void;
}) {
  const name = shortName(component);
  const inspecting = useArchitectUi((s) => s.selectedId === component.id);
  const awaiting = useChangeStore((s) => s.pending?.componentId === component.id);
  const verb = multi ? (selected ? "Remove" : "Add") : selected ? "Installed" : "Replace";
  const Icon = multi ? (selected ? Minus : Plus) : selected ? CircleCheck : Repeat2;
  const intent = selected ? (multi ? "btn-danger" : "btn-tertiary") : conflicts.length ? "btn-tertiary" : "btn-secondary";

  return (
    <li
      data-testid={`option-${component.id}`}
      data-selected={selected ? "true" : "false"}
      data-state={awaiting ? "pending" : selected ? "installed" : conflicts.length ? "incompatible" : "available"}
      className={`relative space-y-2.5 overflow-hidden rounded-lg border p-3 transition-colors ${
        selected ? "border-accent-green/70 bg-accent-green/[0.07]" : "border-border bg-background/40 hover:border-accent-cyan/40"
      } ${inspecting ? "ring-2 ring-accent-cyan ring-offset-2 ring-offset-surface" : ""}`}
    >
      {selected ? <span aria-hidden className="absolute inset-y-0 left-0 w-1 bg-accent-green" /> : null}
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 space-y-0.5">
          <h3 className="break-words text-sm font-semibold">{name}</h3>
          <p className="text-xs text-muted">{component.description}</p>
        </div>
        <div className="flex flex-wrap gap-1">
          {selected ? (
            <span data-testid="state-installed" className="inline-flex items-center gap-1 rounded bg-accent-green px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[#04140d]">
              <CircleCheck aria-hidden className="h-3 w-3" /> Installed
            </span>
          ) : null}
          {inspecting ? (
            <span className="inline-flex items-center gap-1 rounded border border-accent-cyan/60 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-accent-cyan">
              <Eye aria-hidden className="h-3 w-3" /> Inspecting
            </span>
          ) : null}
          {awaiting ? (
            <span className="rounded border border-accent-amber/60 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-accent-amber">
              Awaiting confirmation
            </span>
          ) : null}
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5">
        {keyParameters(category, component).map(([key, q]) => (
          <div key={key} className="min-w-0 space-y-0.5">
            <dt className="text-[11px] text-muted">{humanize(key)}</dt>
            <dd className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-sm">
              <span className="readout font-medium">{formatQuantity(q)}</span>
              {formatQuantity(q) === MISSING ? null : (
                <>
                  <FidelityBadge fidelity={q.provenance.fidelity} />
                  <ProvenancePopover provenance={q.provenance} label={`${name} ${humanize(key).toLowerCase()}`} />
                </>
              )}
            </dd>
          </div>
        ))}
      </dl>

      <p data-testid="compat-indicator" className="flex items-start gap-1.5 text-xs">
        {conflicts.length === 0 ? (
          <>
            <CircleCheck aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent-green" />
            <span>No catalogue rule conflict (re-checked by analysis)</span>
          </>
        ) : (
          <>
            <TriangleAlert aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent-amber" />
            <span className="text-accent-amber">
              Incompatible: conflicts with {Array.from(new Set(conflicts.map((c) => affectedName(c.affectedId)))).join(", ")}.{" "}
              <span className="text-muted">{conflicts[0].message}</span>
            </span>
          </>
        )}
      </p>

      <p data-testid="cost-delta" className="text-xs">
        <span className="text-muted">Catalogue list cost delta: </span>
        <span className="readout font-medium">{delta === null ? `${MISSING} no catalogue cost` : formatSigned(delta, "USD")}</span>
        {delta !== null && component.parameters.cost ? (
          <>
            {" "}
            <FidelityBadge fidelity={component.parameters.cost.provenance.fidelity} />
          </>
        ) : null}
      </p>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          data-testid={`select-${component.id}`}
          aria-pressed={selected}
          aria-label={`${verb} ${name}`}
          disabled={!multi && selected}
          onClick={(e) => onChoose(component, e.currentTarget)}
          className={`btn ${intent}`}
        >
          <Icon aria-hidden className="h-4 w-4" />
          {verb}
        </button>
        <button
          type="button"
          data-testid={`inspect-${component.id}`}
          onClick={() => useArchitectUi.getState().select(component.id, category)}
          className="btn btn-tertiary"
          aria-label={`Details for ${name}`}
        >
          Details
        </button>
      </div>
    </li>
  );
}

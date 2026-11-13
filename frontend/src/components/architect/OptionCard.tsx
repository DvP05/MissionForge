import { CircleCheck, TriangleAlert } from "lucide-react";

import { FidelityBadge } from "@/components/common/FidelityBadge";
import { ProvenancePopover } from "@/components/common/ProvenancePopover";
import { StatusPill } from "@/components/common/StatusPill";
import { formatQuantity, formatSigned, humanize, MISSING } from "@/lib/format";
import type { ComponentCategory } from "@/state/mission-store";
import { KEY_PARAMETERS, type CatalogComponent, type CompatConflict } from "./catalog-helpers";

export function shortName(c: { name: string }): string {
  return c.name.replace(/^Archetype:\s*/, "");
}

/** Catalogue parameters to show: the category's key ones, falling back to the first few. */
function keyParameters(category: ComponentCategory, c: CatalogComponent): [string, CatalogComponent["parameters"][string]][] {
  const wanted = KEY_PARAMETERS[category].filter((k) => k in c.parameters);
  const keys = wanted.length > 0 ? wanted : Object.keys(c.parameters).slice(0, 4);
  return keys.map((k) => [k, c.parameters[k]]);
}

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
  selected: boolean;
  multi: boolean;
  conflicts: CompatConflict[];
  /** Catalogue list cost delta in USD, or null when not available. */
  delta: number | null;
  /** Resolves a conflicting component id to its display name. */
  affectedName: (id: string) => string;
  onChoose: (component: CatalogComponent) => void;
}) {
  const name = shortName(component);
  const verb = multi ? (selected ? "Remove" : "Add") : selected ? "Selected" : "Use";
  return (
    <li
      data-testid={`option-${component.id}`}
      data-selected={selected ? "true" : "false"}
      className={`space-y-3 rounded-lg border p-3 ${selected ? "border-accent-cyan/60 bg-accent-cyan/5" : "border-border"}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 space-y-1">
          <h3 className="break-words text-base font-semibold">{name}</h3>
          <p className="text-sm text-muted">{component.description}</p>
        </div>
        {selected ? <StatusPill tone="info">Selected</StatusPill> : null}
      </div>

      <dl className="grid gap-2 sm:grid-cols-2">
        {keyParameters(category, component).map(([key, q]) => (
          <div key={key} className="space-y-0.5">
            <dt className="text-xs text-muted">{humanize(key)}</dt>
            <dd className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
              <span className="font-medium tabular-nums">{formatQuantity(q)}</span>
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

      <p data-testid="compat-indicator" className="flex items-start gap-1.5 text-sm">
        {conflicts.length === 0 ? (
          <>
            <CircleCheck aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-accent-cyan" />
            <span>No catalogue rule conflict (re-checked by analysis)</span>
          </>
        ) : (
          <>
            <TriangleAlert aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-accent-amber" />
            <span>
              Conflicts with {Array.from(new Set(conflicts.map((c) => affectedName(c.affectedId)))).join(", ")}
            </span>
          </>
        )}
      </p>

      <p data-testid="cost-delta" className="text-sm">
        <span className="text-muted">Catalogue list cost delta: </span>
        <span className="font-medium tabular-nums">{delta === null ? `${MISSING} no catalogue cost` : formatSigned(delta, "USD")}</span>
        {delta !== null && component.parameters.cost ? (
          <>
            {" "}
            <FidelityBadge fidelity={component.parameters.cost.provenance.fidelity} />
          </>
        ) : null}
      </p>

      <button
        type="button"
        data-testid={`select-${component.id}`}
        aria-pressed={selected}
        aria-label={`${verb} ${name}`}
        disabled={!multi && selected}
        onClick={() => onChoose(component)}
        className="inline-flex min-h-11 items-center rounded-lg border border-accent-cyan/60 px-4 text-sm font-medium text-accent-cyan hover:bg-accent-cyan/10 disabled:cursor-default disabled:opacity-60 disabled:hover:bg-transparent"
      >
        {verb}
      </button>
    </li>
  );
}

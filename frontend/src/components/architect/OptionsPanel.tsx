"use client";

import type { ComponentCategory, MissionState } from "@/state/mission-store";
import {
  CATEGORY_ORDER,
  conflictsForCandidate,
  costDelta,
  selectedIds,
  type CatalogComponent,
  type CatalogGroup,
} from "./catalog-helpers";
import { requestChange } from "./component-actions";
import { OptionCard, shortName } from "./OptionCard";
import { TradeoffNote } from "./TradeoffNote";

/**
 * Available components for the active subsystem. Every action goes through requestChange:
 * an add without conflicts applies at once; a replacement, a removal or anything that breaks a
 * catalogue rule asks first (ComponentChangeDialog). No other selection is ever changed.
 */
export function OptionsPanel({
  mission,
  groups,
  index,
  category,
}: {
  mission: MissionState;
  groups: CatalogGroup[];
  index: Map<string, CatalogComponent>;
  category: ComponentCategory;
}) {
  const meta = CATEGORY_ORDER.find((c) => c.category === category)!;
  const group = groups.find((g) => g.category === category);
  const chosen = selectedIds(mission, category);
  const multi = meta.multi === true;
  const nameOf = (id: string) => (index.has(id) ? shortName(index.get(id)!) : id);

  return (
    <section aria-labelledby="options-heading" className="space-y-3" data-testid="options-panel">
      <div className="space-y-1" data-testid="selected-component">
        <h2 id="options-heading" className="text-base font-semibold">
          {meta.label}
        </h2>
        <p className="text-sm">
          <span className="text-muted">{multi ? "Installed instruments: " : "Installed: "}</span>
          <span className="font-medium">{chosen.length === 0 ? "none" : chosen.map(nameOf).join(", ")}</span>
        </p>
        <p className="text-xs text-muted">
          {multi
            ? "Add or remove instruments; each confirmed change is one design revision."
            : "One component fills this slot. Replacing it shows the old and new specifications first."}
        </p>
      </div>
      <TradeoffNote />
      {(group?.components ?? []).length === 0 ? (
        <p className="text-sm text-muted">No catalogue component matches the search in this subsystem.</p>
      ) : null}
      <ul className="space-y-2.5">
        {(group?.components ?? []).map((component) => (
          <OptionCard
            key={component.id}
            category={category}
            component={component}
            selected={chosen.includes(component.id)}
            multi={multi}
            conflicts={
              multi && chosen.includes(component.id) ? [] : conflictsForCandidate(index, mission, category, component.id)
            }
            delta={costDelta(index, mission, category, component)}
            affectedName={nameOf}
            onChoose={(c, opener) => requestChange(index, category, c.id, opener)}
          />
        ))}
      </ul>
    </section>
  );
}

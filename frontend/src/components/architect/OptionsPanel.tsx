"use client";

import { useRef, useState } from "react";

import { useMissionStore, type ComponentCategory, type MissionState } from "@/state/mission-store";
import {
  CATEGORY_ORDER,
  conflictsForCandidate,
  costDelta,
  selectedIds,
  type CatalogComponent,
  type CatalogGroup,
  type CompatConflict,
} from "./catalog-helpers";
import { CompatDialog, type PendingSwap } from "./CompatDialog";
import { OptionCard, shortName } from "./OptionCard";
import { TradeoffNote } from "./TradeoffNote";

/**
 * Centre column: the selected component(s) of a category and the alternatives. Choosing
 * commits one design revision. A choice that breaks another selection is held for
 * confirmation; no other selection is ever changed.
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
  const [pending, setPending] = useState<PendingSwap | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const meta = CATEGORY_ORDER.find((c) => c.category === category)!;
  const group = groups.find((g) => g.category === category);
  const chosen = selectedIds(mission, category);
  const multi = meta.multi === true;
  const nameOf = (id: string) => (index.has(id) ? shortName(index.get(id)!) : id);

  const commit = (component: CatalogComponent) => {
    const store = useMissionStore.getState();
    store.selectComponent(category, component.id);
    store.commitRevision();
  };

  const choose = (component: CatalogComponent) => {
    const removing = multi && chosen.includes(component.id);
    const conflicts: CompatConflict[] = removing
      ? []
      : conflictsForCandidate(index, mission, category, component.id);
    if (conflicts.length === 0) {
      commit(component);
      return;
    }
    opener.current = document.activeElement as HTMLElement | null;
    setPending({ component, conflicts, delta: costDelta(index, mission, category, component) });
  };

  return (
    <section aria-labelledby="options-heading" className="space-y-4" data-testid="options-panel">
      <div className="space-y-1" data-testid="selected-component">
        <h2 id="options-heading" className="text-lg font-semibold">
          {meta.label}
        </h2>
        <p className="text-sm">
          <span className="text-muted">{multi ? "Selected instruments: " : "Selected: "}</span>
          <span className="font-medium">
            {chosen.length === 0 ? "none" : chosen.map(nameOf).join(", ")}
          </span>
        </p>
        {multi ? (
          <p className="text-xs text-muted">Add or remove instruments; each change is one design revision.</p>
        ) : null}
      </div>
      <TradeoffNote />
      <ul className="space-y-3">
        {(group?.components ?? []).map((component) => (
          <OptionCard
            key={component.id}
            category={category}
            component={component}
            selected={chosen.includes(component.id)}
            multi={multi}
            conflicts={
              multi && chosen.includes(component.id)
                ? []
                : conflictsForCandidate(index, mission, category, component.id)
            }
            delta={costDelta(index, mission, category, component)}
            affectedName={nameOf}
            onChoose={choose}
          />
        ))}
      </ul>
      <CompatDialog
        pending={pending}
        nameOf={nameOf}
        onCancel={() => {
          setPending(null);
          opener.current?.focus();
        }}
        onConfirm={() => {
          if (pending) commit(pending.component);
          setPending(null);
          opener.current?.focus();
        }}
      />
    </section>
  );
}

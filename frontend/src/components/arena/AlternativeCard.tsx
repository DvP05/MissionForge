import { Trash2 } from "lucide-react";

import { CATEGORY_ORDER, selectedIds, type CatalogGroup } from "@/components/architect/catalog-helpers";
import type { ComponentCategory, MissionState } from "@/state/mission-store";

const FIELD = {
  launch: "launchVehicleId",
  bus: "busId",
  propulsion: "propulsionId",
  power: "powerId",
  adcs: "adcsId",
  communications: "communicationsId",
  thermal: "thermalId",
  cdh: "cdhId",
  ground: "groundSegmentId",
} as const;

export interface Alternative {
  label: string;
  mission: MissionState;
}

/** Returns a copy of the alternative's mission with one component choice changed. */
export function withComponent(mission: MissionState, category: ComponentCategory, id: string): MissionState {
  if (category === "instrument") {
    const ids = mission.architecture.instrumentIds;
    const next = ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id];
    return { ...mission, architecture: { ...mission.architecture, instrumentIds: next } };
  }
  return { ...mission, architecture: { ...mission.architecture, [FIELD[category]]: id } };
}

/**
 * One alternative design: a copy of the baseline with a lightweight component swap list
 * (a select per subsystem, a checkbox per instrument). Edits never touch the stored baseline.
 */
export function AlternativeCard({
  alternative,
  baseline,
  groups,
  onChange,
  onRemove,
}: {
  alternative: Alternative;
  baseline: MissionState;
  groups: CatalogGroup[];
  onChange: (category: ComponentCategory, id: string) => void;
  onRemove: () => void;
}) {
  const { label, mission } = alternative;
  return (
    <section
      data-testid={`alternative-card-${label}`}
      aria-label={`Alternative ${label}`}
      className="space-y-3 rounded-lg border border-border p-3"
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">Alternative {label}</h3>
        <button
          type="button"
          data-testid={`remove-alternative-${label}`}
          onClick={onRemove}
          aria-label={`Remove Alternative ${label}`}
          className="inline-flex min-h-11 items-center gap-1.5 rounded-lg border border-border px-3 text-sm hover:text-accent-cyan"
        >
          <Trash2 aria-hidden className="h-4 w-4" />
          Remove
        </button>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {CATEGORY_ORDER.filter((c) => !c.multi).map(({ category, label: categoryLabel }) => {
          const options = groups.find((g) => g.category === category)?.components ?? [];
          const current = selectedIds(mission, category)[0];
          const changed = current !== selectedIds(baseline, category)[0];
          const id = `alt-${label}-${category}`;
          return (
            <div key={category} className="space-y-1">
              <label htmlFor={id} className="text-xs text-muted">
                {categoryLabel}
                {changed ? " (changed from baseline)" : ""}
              </label>
              <select
                id={id}
                data-testid={`alt-select-${label}-${category}`}
                value={current}
                onChange={(e) => onChange(category, e.target.value)}
                className="min-h-11 w-full rounded-lg border border-border bg-surface px-2 text-sm"
              >
                {options.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          );
        })}
      </div>
      <fieldset className="space-y-1">
        <legend className="text-xs text-muted">Instruments</legend>
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {(groups.find((g) => g.category === "instrument")?.components ?? []).map((c) => {
            const id = `alt-${label}-inst-${c.id}`;
            return (
              <label key={c.id} htmlFor={id} className="inline-flex min-h-11 items-center gap-2 text-sm">
                <input
                  id={id}
                  type="checkbox"
                  data-testid={`alt-instrument-${label}-${c.id}`}
                  checked={mission.architecture.instrumentIds.includes(c.id)}
                  onChange={() => onChange("instrument", c.id)}
                  className="h-4 w-4"
                />
                {c.name}
              </label>
            );
          })}
        </div>
      </fieldset>
    </section>
  );
}

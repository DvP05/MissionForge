"use client";

import { useArchitectUi } from "@/state/architect-ui-store";
import type { MissionState } from "@/state/mission-store";
import { CATEGORY_ORDER, selectedIds, type CatalogComponent } from "./catalog-helpers";
import { requestChange } from "./component-actions";
import { shortName } from "./OptionCard";

/**
 * Textual component tree of the current design (design_update.md 6.6): every subsystem and
 * what is installed in it, with Details / Replace / Remove. Also the accessible alternative to
 * the 3D spacecraft.
 */
export function InstalledComponents({ mission, index }: { mission: MissionState; index: Map<string, CatalogComponent> }) {
  const ui = useArchitectUi.getState;
  return (
    <section aria-labelledby="installed-heading" data-testid="installed-components" className="space-y-2">
      <h2 id="installed-heading" className="text-base font-semibold">
        Installed on this design (revision {mission.designRevision})
      </h2>
      <ul className="space-y-2">
        {CATEGORY_ORDER.map(({ category, label, multi }) => {
          const ids = selectedIds(mission, category);
          return (
            <li key={category} className="rounded-lg border border-border bg-background/40 p-2.5">
              <p className="text-[11px] uppercase tracking-wider text-muted">{label}</p>
              {ids.length === 0 ? (
                <p className="text-sm text-accent-red">Empty: nothing installed</p>
              ) : (
                <ul className="mt-1 space-y-1">
                  {ids.map((id) => {
                    const c = index.get(id);
                    return (
                      <li key={id} data-testid={`installed-${id}`} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                        <span className="min-w-0 font-medium">{c ? shortName(c) : `${id} (not in catalogue)`}</span>
                        <span className="flex gap-1">
                          <button type="button" className="btn btn-tertiary min-h-8 px-2 text-xs" onClick={() => ui().select(id, category)}>
                            Details
                          </button>
                          {multi ? (
                            <button
                              type="button"
                              data-testid={`installed-remove-${id}`}
                              className="btn btn-danger min-h-8 px-2 text-xs"
                              onClick={(e) => requestChange(index, category, id, e.currentTarget)}
                            >
                              Remove
                            </button>
                          ) : (
                            <button type="button" className="btn btn-secondary min-h-8 px-2 text-xs" onClick={() => ui().setCategory(category)}>
                              Replace…
                            </button>
                          )}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

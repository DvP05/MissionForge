"use client";

import { Search } from "lucide-react";
import { useMemo, useState } from "react";

import { useArchitectUi, type PanelTab } from "@/state/architect-ui-store";
import type { MissionState } from "@/state/mission-store";
import { CATEGORY_ORDER, type CatalogComponent, type CatalogGroup } from "./catalog-helpers";
import { ComponentInspector } from "./ComponentInspector";
import { InstalledComponents } from "./InstalledComponents";
import { OptionsPanel } from "./OptionsPanel";

const matches = (c: CatalogComponent, q: string) =>
  [c.name, c.description, c.id, ...(c.tags ?? []), ...(c.capabilities ?? [])].some((t) => t.toLowerCase().includes(q));

const TABS: { tab: PanelTab; label: string }[] = [
  { tab: "available", label: "Available" },
  { tab: "installed", label: "Installed" },
  { tab: "details", label: "Details" },
];

/**
 * Right-hand component panel (design_update.md 6.1 C): the active subsystem's available
 * components (with search), the installed component tree, and the inspector.
 */
export function ComponentCatalogue({
  mission,
  groups,
  index,
}: {
  mission: MissionState;
  groups: CatalogGroup[];
  index: Map<string, CatalogComponent>;
}) {
  const category = useArchitectUi((s) => s.category);
  const tab = useArchitectUi((s) => s.panelTab);
  const setTab = useArchitectUi((s) => s.setPanelTab);
  const setCategory = useArchitectUi((s) => s.setCategory);
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();

  const filtered = useMemo(
    () => (q ? groups.map((g) => ({ ...g, components: g.components.filter((c) => matches(c, q)) })) : groups),
    [groups, q],
  );
  const elsewhere = q ? filtered.filter((g) => g.category !== category && g.components.length > 0) : [];

  return (
    <section id="component-panel" aria-label="Components" data-testid="component-catalogue" className="panel space-y-3 p-3">
      <div role="tablist" aria-label="Component panel" className="grid grid-cols-3 gap-1 rounded-lg border border-border bg-background/60 p-1">
        {TABS.map((t) => (
          <button
            key={t.tab}
            type="button"
            role="tab"
            id={`panel-tab-${t.tab}`}
            data-testid={`panel-tab-${t.tab}`}
            aria-selected={tab === t.tab}
            aria-controls={`panel-${t.tab}`}
            onClick={() => setTab(t.tab)}
            className={`min-h-9 rounded-md text-sm font-medium ${tab === t.tab ? "bg-elevated text-accent-cyan" : "text-muted hover:text-foreground"}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div id="panel-available" role="tabpanel" aria-labelledby="panel-tab-available" hidden={tab !== "available"} className="space-y-3">
        <label className="flex items-center gap-2 rounded-lg border border-border bg-background/60 px-3 focus-within:border-accent-cyan/60">
          <Search aria-hidden className="h-4 w-4 text-muted" />
          <span className="sr-only">Search components</span>
          <input
            type="search"
            data-testid="catalogue-search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. spectrometer, high-gain"
            className="min-h-10 w-full bg-transparent text-sm outline-none placeholder:text-muted"
          />
        </label>
        {elsewhere.length > 0 ? (
          <p className="text-xs text-muted">
            Also matching:{" "}
            {elsewhere.map((g, i) => (
              <span key={g.category}>
                {i > 0 ? ", " : ""}
                <button type="button" className="text-accent-cyan underline-offset-2 hover:underline" onClick={() => setCategory(g.category)}>
                  {CATEGORY_ORDER.find((c) => c.category === g.category)?.label} ({g.components.length})
                </button>
              </span>
            ))}
          </p>
        ) : null}
        <div className="lg:max-h-[46rem] lg:overflow-y-auto lg:pr-1">
          <OptionsPanel mission={mission} groups={filtered} index={index} category={category} />
        </div>
      </div>
      <div id="panel-installed" role="tabpanel" aria-labelledby="panel-tab-installed" hidden={tab !== "installed"}>
        {tab === "installed" ? <InstalledComponents mission={mission} index={index} /> : null}
      </div>
      <div id="panel-details" role="tabpanel" aria-labelledby="panel-tab-details" hidden={tab !== "details"}>
        {tab === "details" ? <ComponentInspector mission={mission} index={index} /> : null}
      </div>
    </section>
  );
}

"use client";

import { useState, type ReactNode } from "react";

export interface DetailTab {
  id: string;
  label: string;
  content: ReactNode;
}

/**
 * Tabbed engineering-detail bay: deep-dive panels (explanation and change log, traceability
 * graph, observation schedule) share one area instead of stacking down the page. Inactive
 * panels stay mounted but hidden, so their state survives switching.
 */
export function DetailTabs({ tabs, active, onChange }: { tabs: DetailTab[]; active?: string; onChange?: (id: string) => void }) {
  const [own, setOwn] = useState(tabs[0]?.id ?? "");
  const current = active ?? own;
  const select = (id: string) => (onChange ? onChange(id) : setOwn(id));
  return (
    <section aria-label="Engineering detail" className="panel" data-testid="detail-tabs">
      <div role="tablist" aria-label="Engineering detail" className="flex flex-wrap border-b border-border bg-background-2">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`detail-tab-${t.id}`}
            aria-selected={current === t.id}
            aria-controls={`detail-panel-${t.id}`}
            data-testid={`detail-tab-${t.id}`}
            onClick={() => select(t.id)}
            className={`min-h-10 border-t-2 px-4 font-mono text-xs uppercase tracking-wider ${
              current === t.id ? "border-signal bg-elevated text-foreground" : "border-transparent text-muted hover:text-foreground"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tabs.map((t) => (
        <div key={t.id} id={`detail-panel-${t.id}`} role="tabpanel" aria-labelledby={`detail-tab-${t.id}`} hidden={current !== t.id} className="p-4">
          {t.content}
        </div>
      ))}
    </section>
  );
}

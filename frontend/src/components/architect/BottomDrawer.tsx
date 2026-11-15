"use client";

import { useMissionStore } from "@/state/mission-store";
import { CATEGORY_ORDER, type CatalogComponent } from "./catalog-helpers";
import { shortName } from "./OptionCard";

/**
 * Bottom drawer: explanation of the chosen constraint, the analysis assumptions, and the
 * design changes committed this session (from the store).
 */
export function BottomDrawer({
  explainId,
  index,
}: {
  explainId: string | null;
  index: Map<string, CatalogComponent>;
}) {
  const analysis = useMissionStore((s) => s.analysis);
  const changeLog = useMissionStore((s) => s.changeLog);
  const constraint = analysis?.constraints.find((c) => c.id === explainId);
  const name = (id: string | null) => (id === null ? "none" : index.has(id) ? shortName(index.get(id)!) : id);
  const label = (category: string) => CATEGORY_ORDER.find((c) => c.category === category)?.label ?? category;

  return (
    <section
      aria-label="Details: explanation, provenance and recent changes"
      data-testid="bottom-drawer"
      className="grid gap-4 lg:grid-flow-dense lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]"
    >
      <div className="space-y-2">
        <h2 className="text-sm font-semibold">Explanation</h2>
        <p data-testid="drawer-explanation" className="text-sm">
          {constraint
            ? `${constraint.label}: ${constraint.explanation}`
            : "Choose Explain on a constraint to read why it has its status."}
        </p>
      </div>
      <div className="space-y-2 lg:col-start-2 lg:row-span-2 lg:row-start-1">
        <h2 className="text-sm font-semibold">
          Provenance and assumptions{analysis ? ` (${analysis.assumptions.length})` : ""}
        </h2>
        {analysis && analysis.assumptions.length > 0 ? (
          <div tabIndex={0} role="region" aria-label="Engine assumptions (scrolls)" className="max-h-[26rem] overflow-y-auto border border-border bg-background-2 p-3">
          <ul className="list-disc gap-6 space-y-1 pl-4 text-xs leading-relaxed md:columns-2">
            {analysis.assumptions.map((a) => (
              <li key={a} data-testid="drawer-assumption">
                {a}
              </li>
            ))}
          </ul>
          </div>
        ) : (
          <p className="text-sm text-muted">Assumptions appear with the first analysis.</p>
        )}
        {analysis ? (
          <p className="text-xs text-muted">
            Engine {analysis.engineVersion}, catalogue {analysis.catalogVersion}
          </p>
        ) : null}
      </div>
      <div className="space-y-2">
        <h2 className="text-sm font-semibold">Recent design changes</h2>
        {changeLog.length === 0 ? (
          <p className="text-sm text-muted">No changes yet in this session.</p>
        ) : (
          <ol className="space-y-1 text-sm">
            {changeLog.map((c, i) => (
              <li key={`${c.revision}-${c.category}-${i}`} data-testid="drawer-change">
                <span className="text-muted">Revision {c.revision}: </span>
                {label(c.category)}: {name(c.fromId)} to {name(c.toId)}
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}

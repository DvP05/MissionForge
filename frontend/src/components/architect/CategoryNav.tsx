"use client";

import { constraintsFor, constraintStatus, type EngStatus } from "@/lib/spacecraft/engineering-status";
import { GROUP_COLOUR, GROUP_OF } from "@/lib/spacecraft/part-registry";
import { useMissionStore, type ComponentCategory, type MissionState } from "@/state/mission-store";
import { CATEGORY_ORDER, selectedIds, type CatalogComponent } from "./catalog-helpers";
import { EngStatusChip } from "./EngStatusChip";

const RANK: Record<EngStatus, number> = { FAIL: 0, WATCH: 1, "NOT MODELLED": 2, PASS: 3, ANALYSING: 4, STALE: 5 };

/**
 * Subsystem build tree (design_update.md 6.1 A). Each subsystem names what is installed, how
 * many parts it holds, whether the mission needs it, and its worst analysed constraint status
 * for the current revision (STALE / ANALYSING while a newer revision is checked).
 */
export function CategoryNav({
  mission,
  index,
  active,
  onSelect,
}: {
  mission: MissionState;
  index: Map<string, CatalogComponent>;
  active: ComponentCategory;
  onSelect: (category: ComponentCategory) => void;
}) {
  const analysis = useMissionStore((s) => s.analysis);
  const analysisRevision = useMissionStore((s) => s.analysisRevision);
  const status = useMissionStore((s) => s.status);
  const current = analysis !== null && analysisRevision === mission.designRevision;

  const stateOf = (category: ComponentCategory, ids: string[]): EngStatus | "EMPTY" | null => {
    if (ids.length === 0 || ids.some((id) => !index.has(id))) return "EMPTY";
    if (status === "calculating") return "ANALYSING";
    if (!analysis) return null;
    if (!current) return "STALE";
    const related = constraintsFor(analysis.constraints, category).map(constraintStatus);
    if (related.length === 0) return null;
    return related.sort((a, b) => RANK[a] - RANK[b])[0];
  };

  return (
    <nav aria-label="Subsystems">
      <ul className="grid grid-cols-2 gap-1.5 lg:grid-cols-1">
        {CATEGORY_ORDER.map(({ category, label }) => {
          const ids = selectedIds(mission, category);
          const installed =
            category === "instrument"
              ? `${ids.length} installed`
              : (index.get(ids[0])?.name ?? ids[0] ?? "empty").replace(/^Archetype:\s*/, "");
          const st = stateOf(category, ids);
          const isActive = category === active;
          return (
            <li key={category}>
              <button
                type="button"
                data-testid={`category-nav-${category}`}
                data-state={st ?? "none"}
                aria-current={isActive ? "true" : undefined}
                onClick={() => onSelect(category)}
                className={`group flex min-h-12 w-full items-stretch gap-2 rounded-lg border text-left text-sm transition-colors ${
                  isActive ? "border-accent-cyan/70 bg-accent-cyan/10" : "border-border bg-background/40 hover:border-accent-cyan/40"
                }`}
              >
                <span aria-hidden className="w-1 shrink-0 rounded-l-lg" style={{ background: GROUP_COLOUR[GROUP_OF[category]] }} />
                <span className="flex min-w-0 flex-1 flex-col justify-center py-1.5 pr-2">
                  <span className="flex flex-wrap items-center justify-between gap-1">
                    <span className={`font-medium ${isActive ? "text-accent-cyan" : ""}`}>{label}</span>
                    {st === "EMPTY" ? (
                      <span className="rounded border border-accent-red/60 px-1 text-[10px] font-semibold text-accent-red">EMPTY</span>
                    ) : st ? (
                      <EngStatusChip status={st} />
                    ) : null}
                  </span>
                  <span className="w-full truncate text-xs text-muted">{installed}</span>
                  <span className="text-[10px] uppercase tracking-wider text-muted">
                    {category === "ground" ? "Required · not on spacecraft" : category === "instrument" ? "Required · at least one" : "Required"}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

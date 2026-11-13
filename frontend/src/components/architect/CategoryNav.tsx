import type { ComponentCategory, MissionState } from "@/state/mission-store";
import { CATEGORY_ORDER, selectedIds, type CatalogComponent } from "./catalog-helpers";

/** Subsystem navigation. Each button names the category and its current selection. */
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
  return (
    <nav aria-label="Subsystems">
      <ul className="grid grid-cols-2 gap-2 lg:grid-cols-1">
        {CATEGORY_ORDER.map(({ category, label }) => {
          const ids = selectedIds(mission, category);
          const current =
            category === "instrument"
              ? `${ids.length} selected`
              : (index.get(ids[0])?.name ?? ids[0]).replace(/^Archetype:\s*/, "");
          return (
            <li key={category}>
              <button
                type="button"
                data-testid={`category-nav-${category}`}
                aria-current={category === active ? "true" : undefined}
                onClick={() => onSelect(category)}
                className={`flex min-h-11 w-full flex-col items-start justify-center rounded-lg border px-3 py-1.5 text-left text-sm ${
                  category === active
                    ? "border-accent-cyan/60 bg-accent-cyan/10 text-accent-cyan"
                    : "border-border text-foreground hover:border-accent-cyan/40"
                }`}
              >
                <span className="font-medium">{label}</span>
                <span className="w-full truncate text-xs text-muted">{current}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

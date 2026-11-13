import { ArrowLeftRight } from "lucide-react";

import { Metric } from "./Metric";
import type { TileModel } from "./tile-model";

/** One budget group. `previous` is only used to flag and describe a change. */
export function BudgetTile({
  tile,
  previous,
  changed,
  reason,
}: {
  tile: TileModel;
  previous?: TileModel;
  changed: boolean;
  reason: string;
}) {
  const allMissing = tile.rows.every((r) => r.text === null);
  return (
    <section
      data-testid={`budget-tile-${tile.id}`}
      data-changed={changed ? "true" : "false"}
      aria-label={tile.title}
      className={`rounded-lg border p-3 ${changed ? "border-accent-cyan/70 bg-accent-cyan/5" : "border-border"}`}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{tile.title}</h3>
        {changed ? (
          <span
            data-testid="changed-marker"
            className="inline-flex items-center gap-1 text-xs font-medium text-accent-cyan"
          >
            <ArrowLeftRight aria-hidden className="h-3.5 w-3.5" />
            Changed
          </span>
        ) : null}
      </div>
      <dl className="space-y-2">
        {tile.rows.map((row, i) => {
          const before = previous?.rows[i];
          const differs = changed && before !== undefined && before.raw !== row.raw;
          return (
            <Metric
              key={row.key}
              label={row.label}
              text={row.text}
              provenance={row.provenance}
              reason={allMissing && i > 0 ? "" : (row.reason ?? reason)}
              was={differs ? (before.text ?? "—") : null}
            />
          );
        })}
      </dl>
    </section>
  );
}

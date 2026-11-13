"use client";

import type { ScienceObjective } from "@/state/mission-store";

export const MAX_OBJECTIVES = 3;

const PRIORITIES: { value: number; label: string }[] = [
  { value: 0.5, label: "Low (0.5)" },
  { value: 1, label: "Medium (1)" },
  { value: 1.5, label: "High (1.5)" },
  { value: 2, label: "Top (2)" },
];

export interface ObjectiveChoice {
  objective: ScienceObjective;
  selected: boolean;
}

/** Confirm or edit the mission's 2-3 science objectives; each change is one design revision. */
export function ObjectiveSelector({
  choices,
  onToggle,
  onPriority,
}: {
  choices: readonly ObjectiveChoice[];
  onToggle: (objective: ScienceObjective, selected: boolean) => void;
  onPriority: (objectiveId: string, priority: number) => void;
}) {
  const selectedCount = choices.filter((c) => c.selected).length;
  const full = selectedCount >= MAX_OBJECTIVES;
  return (
    <section aria-labelledby="objectives-heading" className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="objectives-heading" className="text-lg font-semibold">
          Science objectives
        </h2>
        <p data-testid="objective-selected-count" className="text-sm text-muted">
          {selectedCount} of {MAX_OBJECTIVES} objectives selected
        </p>
      </div>
      <p className="text-sm text-muted">
        Keep two or three.{" "}
        {full ? "Deselect one to swap in another." : "Add an optional objective to widen the science."}
      </p>
      <ul className="space-y-2">
        {choices.map(({ objective, selected }) => {
          const onlyOne = selected && selectedCount <= 1;
          const blocked = onlyOne || (!selected && full);
          const checkboxId = `objective-check-${objective.id}`;
          const priorityId = `objective-priority-${objective.id}`;
          const options = PRIORITIES.some((p) => p.value === objective.priority)
            ? PRIORITIES
            : [...PRIORITIES, { value: objective.priority, label: `Custom (${objective.priority})` }];
          return (
            <li
              key={objective.id}
              data-testid={`objective-${objective.id}`}
              className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-3 sm:flex-row sm:items-start"
            >
              <div className="flex min-w-0 flex-1 items-start gap-3">
                <input
                  id={checkboxId}
                  type="checkbox"
                  checked={selected}
                  disabled={blocked}
                  onChange={(e) => onToggle(objective, e.target.checked)}
                  className="mt-1 h-5 w-5 shrink-0 accent-cyan-400"
                />
                <label htmlFor={checkboxId} className="min-w-0 flex-1">
                  <span className="block font-medium">{objective.title}</span>
                  <span className="block text-sm text-muted">{objective.question}</span>
                  {onlyOne ? (
                    <span className="block text-xs text-muted">At least one objective is required.</span>
                  ) : null}
                </label>
              </div>
              {selected ? (
                <div className="flex items-center gap-2 text-sm">
                  <label htmlFor={priorityId} className="text-muted">
                    Priority weight
                  </label>
                  <select
                    id={priorityId}
                    value={String(objective.priority)}
                    onChange={(e) => onPriority(objective.id, Number(e.target.value))}
                    className="min-h-11 rounded-lg border border-border bg-background px-2"
                  >
                    {options.map((p) => (
                      <option key={p.value} value={String(p.value)}>
                        {p.label}
                      </option>
                    ))}
                  </select>
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

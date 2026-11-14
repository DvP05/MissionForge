"use client";

import { Lightbulb, X } from "lucide-react";

import { CONCEPTS, type Concept } from "@/lib/learning/concepts";
import { useLocalValue } from "@/lib/learning/useLocalValue";

const KEYS: Record<Concept["id"], string> = {
  // LO-1 keeps its original key so earlier dismissals still hold.
  lo1: "missionforge:concept-dismissed:lo1-objectives-to-requirements",
  lo2: "missionforge:concept-dismissed:lo2",
  lo3: "missionforge:concept-dismissed:lo3",
  lo4: "missionforge:concept-dismissed:lo4",
  lo5: "missionforge:concept-dismissed:lo5",
  lo6: "missionforge:concept-dismissed:lo6",
  lo7: "missionforge:concept-dismissed:lo7",
};

/** Just-in-time, dismissible, non-blocking concept card (Task 7.3, F-021). */
export function ConceptCard({ id }: { id: Concept["id"] }) {
  const [dismissed, setDismissed] = useLocalValue(KEYS[id]);
  if (dismissed === "1") return null;
  const c = CONCEPTS[id];
  return (
    <aside
      data-testid={`concept-card-${id}`}
      aria-labelledby={`concept-${id}-title`}
      className="flex items-start gap-3 rounded-xl border border-accent-cyan/40 bg-surface p-4"
    >
      <Lightbulb aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-accent-cyan" />
      <div className="min-w-0 flex-1 space-y-1">
        <h2 id={`concept-${id}-title`} className="text-sm font-semibold">
          {c.title}
        </h2>
        <p className="text-sm text-muted">{c.body}</p>
      </div>
      <button
        type="button"
        aria-label="Dismiss concept card"
        onClick={() => setDismissed("1")}
        className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-muted hover:text-foreground"
      >
        <X aria-hidden className="h-4 w-4" />
      </button>
    </aside>
  );
}

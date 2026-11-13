"use client";

import { Lightbulb, X } from "lucide-react";
import { useState } from "react";

const STORAGE_KEY = "missionforge:concept-dismissed:lo1-objectives-to-requirements";

function readDismissed(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function writeDismissed() {
  try {
    window.localStorage.setItem(STORAGE_KEY, "1");
  } catch {
    // Storage unavailable: the card still closes for this session.
  }
}

/** Just-in-time concept card (LO-1). Rendered only after the workspace has mounted in the browser. */
export function ConceptCard() {
  const [dismissed, setDismissed] = useState(readDismissed);
  if (dismissed) return null;
  return (
    <aside
      data-testid="concept-card-lo1"
      aria-labelledby="concept-lo1-title"
      className="flex items-start gap-3 rounded-xl border border-accent-cyan/40 bg-surface p-4"
    >
      <Lightbulb aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-accent-cyan" />
      <div className="min-w-0 flex-1 space-y-1">
        <h2 id="concept-lo1-title" className="text-sm font-semibold">
          Why science objectives become measurable requirements
        </h2>
        <p className="text-sm text-muted">
          A science question such as &ldquo;what is it made of?&rdquo; cannot be built or tested. Each objective is
          broken into measurements an instrument can make, so the design can be checked against them.
        </p>
      </div>
      <button
        type="button"
        aria-label="Dismiss concept card"
        onClick={() => {
          writeDismissed();
          setDismissed(true);
        }}
        className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-muted hover:text-foreground"
      >
        <X aria-hidden className="h-4 w-4" />
      </button>
    </aside>
  );
}

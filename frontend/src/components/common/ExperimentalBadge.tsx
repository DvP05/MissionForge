import { FlaskConical } from "lucide-react";

/** Shown wherever a run launched despite failing hard constraints. */
export function ExperimentalBadge() {
  return (
    <p
      data-testid="experimental-badge"
      role="note"
      className="inline-flex items-center gap-2 rounded-lg border border-accent-amber/60 bg-accent-amber/10 px-3 py-1.5 text-sm font-medium text-accent-amber"
    >
      <FlaskConical aria-hidden className="h-4 w-4 shrink-0" />
      Experimental run — design violates hard limits
    </p>
  );
}

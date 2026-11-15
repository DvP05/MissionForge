import { useMissionStore } from "@/state/mission-store";
import { analysisFailed, analysisProvenance } from "@/components/budgets/tile-model";
import { ConstraintCard, type Constraint } from "./ConstraintCard";

const RANK: Record<Constraint["status"], number> = { fail: 0, warning: 1, "not-modelled": 2, pass: 3 };

/** Display order only: failures first, then by the backend severity. */
function ordered(constraints: Constraint[]): Constraint[] {
  return [...constraints].sort((a, b) => RANK[a.status] - RANK[b.status] || b.severity - a.severity);
}

export function ConstraintPanel({
  selectedId,
  onExplain,
}: {
  selectedId: string | null;
  onExplain: (id: string) => void;
}) {
  const analysis = useMissionStore((s) => s.analysis);
  return (
    <section aria-labelledby="constraints-heading" className="space-y-3" data-testid="constraint-panel">
      <h2 id="constraints-heading" className="text-lg font-semibold">
        Constraints
      </h2>
      {analysis ? (
        <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {ordered(analysis.constraints).map((c) => (
            <ConstraintCard key={c.id} constraint={c} selected={c.id === selectedId} marginProvenance={analysisFailed(analysis) ? null : analysisProvenance(analysis)} onExplain={onExplain} />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted">Constraint results appear once the backend analysis arrives.</p>
      )}
    </section>
  );
}

"use client";

import { useState } from "react";

import { useMissionStore, type MissionAnalysis } from "@/state/mission-store";
import { AnalysisStatus } from "./AnalysisStatus";
import { BudgetTile } from "./BudgetTile";
import { FeasibilityCard } from "./FeasibilityCard";
import { buildTiles, placeholderTiles, tileChanged } from "./tile-model";

/** The analysis before the current one, kept only to highlight what changed. */
function usePreviousAnalysis(analysis: MissionAnalysis | null): MissionAnalysis | null {
  const [pair, setPair] = useState<{ current: MissionAnalysis | null; previous: MissionAnalysis | null }>({
    current: analysis,
    previous: null,
  });
  if (analysis !== pair.current) {
    setPair({ current: analysis, previous: pair.current });
    return pair.current;
  }
  return pair.previous;
}

export function BudgetPanel({ onRetry }: { onRetry: () => void }) {
  const analysis = useMissionStore((s) => s.analysis);
  const status = useMissionStore((s) => s.status);
  const designRevision = useMissionStore((s) => s.designRevision);
  const previous = usePreviousAnalysis(analysis);

  const tiles = analysis ? buildTiles(analysis) : placeholderTiles();
  const prevTiles = previous ? buildTiles(previous) : null;
  const reason =
    status === "error"
      ? "Analysis failed and no earlier result exists"
      : status === "calculating"
        ? "Analysis in progress"
        : "Not analysed yet";
  const feasibilityChanged =
    !!analysis &&
    !!previous &&
    (previous.feasibility !== analysis.feasibility || previous.missionReady !== analysis.missionReady);

  return (
    <section aria-labelledby="budgets-heading" className="space-y-3" data-testid="budget-panel">
      <h2 id="budgets-heading" className="text-lg font-semibold">
        Live budgets
      </h2>
      <AnalysisStatus analysis={analysis} status={status} designRevision={designRevision} onRetry={onRetry} />
      <FeasibilityCard analysis={analysis} changed={feasibilityChanged} reason={reason} />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1 2xl:grid-cols-2">
        {tiles.map((tile) => {
          const prev = prevTiles?.find((p) => p.id === tile.id);
          return (
            <BudgetTile
              key={tile.id}
              tile={tile}
              previous={prev}
              changed={analysis !== null && tileChanged(prev, tile)}
              reason={reason}
            />
          );
        })}
      </div>
    </section>
  );
}

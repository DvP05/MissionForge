"use client";

import { useMissionStore } from "@/state/mission-store";

/** One sentence on the biggest current trade-off, taken from the backend's top driver. */
export function TradeoffNote() {
  const analysis = useMissionStore((s) => s.analysis);
  if (!analysis) {
    return (
      <p data-testid="tradeoff-note" className="text-sm text-muted">
        The biggest trade-off appears once the backend analysis arrives.
      </p>
    );
  }
  const driver = analysis.constraints.find((c) => c.id === analysis.topDrivers[0]);
  const action = driver?.suggestedActions?.[0];
  return (
    <p data-testid="tradeoff-note" className="rounded-lg border border-border p-3 text-sm">
      <span className="font-medium">Biggest trade-off: </span>
      {driver
        ? `${driver.label} is the top driver. ${action ? `${action.label}: ${action.expectedEffect}` : driver.explanation}`
        : "No constraint is failing or on watch, so no trade-off currently dominates."}
    </p>
  );
}

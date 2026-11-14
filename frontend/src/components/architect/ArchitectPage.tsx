"use client";

import { useState } from "react";

import { ErrorState, LoadingState } from "@/components/common/States";
import { LaunchPanel } from "@/components/mission-control/LaunchPanel";
import { Counterfactual } from "@/components/review/Counterfactual";
import { ScheduleBoard } from "@/components/schedule/ScheduleBoard";
import { GraphExplorer } from "@/components/science-traceability/GraphExplorer";
import { BudgetPanel } from "@/components/budgets/BudgetPanel";
import { useAnalysis } from "@/hooks/useAnalysis";
import { useMissionStore, type ComponentCategory } from "@/state/mission-store";
import { BottomDrawer } from "./BottomDrawer";
import { CategoryNav } from "./CategoryNav";
import { ConstraintPanel } from "./ConstraintPanel";
import { OptionsPanel } from "./OptionsPanel";
import { useCatalog } from "./useCatalog";

/**
 * Architect screen. Desktop: 22 / 48 / 30 columns (subsystem navigation, component
 * options, live budgets and constraints) plus a bottom drawer. Mobile: stacked.
 */
export function ArchitectPage() {
  const mission = useMissionStore((s) => s.mission);
  const { retry: retryAnalysis } = useAnalysis();
  const { catalog, retry: retryCatalog } = useCatalog();
  const [category, setCategory] = useState<ComponentCategory>("communications");
  const [explainId, setExplainId] = useState<string | null>(null);

  if (!mission) return <LoadingState label="Loading mission" />;
  if (catalog.kind === "loading") return <LoadingState label="Loading component catalogue" />;
  if (catalog.kind === "error") {
    return <ErrorState title="Component catalogue unavailable" message={catalog.message} onRetry={retryCatalog} />;
  }

  return (
    <div className="space-y-4" data-testid="architect-page">
      <LaunchPanel />
      <div className="grid gap-4 lg:grid-cols-[22fr_48fr_30fr]">
        <aside aria-label="Subsystem selection" data-testid="architect-left" className="min-w-0">
          <CategoryNav mission={mission} index={catalog.index} active={category} onSelect={setCategory} />
        </aside>
        <div data-testid="architect-center" className="min-w-0">
          <OptionsPanel mission={mission} groups={catalog.groups} index={catalog.index} category={category} />
        </div>
        <aside aria-label="Budgets and constraints" data-testid="architect-right" className="min-w-0 space-y-6">
          <BudgetPanel onRetry={retryAnalysis} />
          <ConstraintPanel selectedId={explainId} onExplain={setExplainId} />
          <Counterfactual />
        </aside>
      </div>
      <BottomDrawer explainId={explainId} index={catalog.index} />
      <GraphExplorer />
      <ScheduleBoard />
    </div>
  );
}

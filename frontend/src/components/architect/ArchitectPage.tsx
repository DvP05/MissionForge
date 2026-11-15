"use client";

import { Boxes, Gauge, Rocket } from "lucide-react";
import { useState } from "react";

import { ErrorState, LoadingState } from "@/components/common/States";
import { ConceptCard } from "@/components/learning/ConceptCard";
import { PredictionPrompt } from "@/components/learning/Prediction";
import { LaunchPanel } from "@/components/mission-control/LaunchPanel";
import { Counterfactual } from "@/components/review/Counterfactual";
import { ScheduleBoard } from "@/components/schedule/ScheduleBoard";
import { GraphExplorer } from "@/components/science-traceability/GraphExplorer";
import { SpacecraftStage } from "@/components/spacecraft3d/SpacecraftStage";
import { BudgetPanel } from "@/components/budgets/BudgetPanel";
import { useAnalysis } from "@/hooks/useAnalysis";
import { useArchitectUi, type MobileTab } from "@/state/architect-ui-store";
import { useMissionStore } from "@/state/mission-store";
import { BottomDrawer } from "./BottomDrawer";
import { CategoryNav } from "./CategoryNav";
import { ComponentCatalogue } from "./ComponentCatalogue";
import { ComponentChangeDialog } from "./ComponentChangeDialog";
import { ConstraintPanel } from "./ConstraintPanel";
import { DetailTabs } from "./DetailTabs";
import { EngineeringDashboard, LiveBudgetRail } from "./EngineeringDashboard";
import { ImpactReport } from "./ImpactReport";
import { OperationsPanel } from "./OperationsPanel";
import { ReadinessBoard } from "./ReadinessBoard";
import { useCatalog } from "./useCatalog";

const MOBILE_TABS: { tab: MobileTab; label: string; Icon: typeof Boxes }[] = [
  { tab: "build", label: "Build", Icon: Boxes },
  { tab: "spacecraft", label: "Spacecraft", Icon: Rocket },
  { tab: "budgets", label: "Budgets", Icon: Gauge },
];

/**
 * Mission Architect (design_update.md section 6). Desktop: subsystem rail / spacecraft
 * assembly stage / component panel at about 22 / 48 / 30, the impact report and readiness gates
 * under the spacecraft, and a persistent live-budget rail. Narrow screens show one zone at a
 * time (Build, Spacecraft, Budgets) and keep every action. All engineering values are the
 * backend analysis of the current revision.
 */
export function ArchitectPage() {
  const mission = useMissionStore((s) => s.mission);
  const { retry: retryAnalysis } = useAnalysis();
  const { catalog, retry: retryCatalog } = useCatalog();
  const category = useArchitectUi((s) => s.category);
  const setCategory = useArchitectUi((s) => s.setCategory);
  const mobileTab = useArchitectUi((s) => s.mobileTab);
  const setMobileTab = useArchitectUi((s) => s.setMobileTab);
  const [explainId, setExplainId] = useState<string | null>(null);
  const [detailTab, setDetailTab] = useState("explain");
  // "Explain" on a constraint opens its explanation in the detail bay
  const explain = (id: string) => {
    setExplainId(id);
    setDetailTab("explain");
    requestAnimationFrame(() => document.getElementById("detail-panel-explain")?.scrollIntoView({ block: "nearest" }));
  };

  if (!mission) return <LoadingState label="Loading mission" />;
  if (catalog.kind === "loading") return <LoadingState label="Loading component catalogue" />;
  if (catalog.kind === "error") {
    return <ErrorState title="Component catalogue unavailable" message={catalog.message} onRetry={retryCatalog} />;
  }
  const show = (tab: MobileTab) => (mobileTab === tab ? "" : "max-lg:hidden");

  return (
    <div className="space-y-4" data-testid="architect-page">
      <LaunchPanel />

      <div role="tablist" aria-label="Architect view" className="sticky top-16 z-20 grid grid-cols-3 gap-1 rounded-lg border border-border bg-background/90 p-1 backdrop-blur lg:hidden">
        {MOBILE_TABS.map(({ tab, label, Icon }) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={mobileTab === tab}
            data-testid={`mobile-tab-${tab}`}
            onClick={() => setMobileTab(tab)}
            className={`inline-flex min-h-10 items-center justify-center gap-1.5 rounded-md text-sm font-medium ${
              mobileTab === tab ? "bg-elevated text-accent-cyan" : "text-muted"
            }`}
          >
            <Icon aria-hidden className="h-4 w-4" /> {label}
          </button>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[22fr_48fr_30fr]">
        <aside aria-label="Subsystems" data-testid="architect-left" className={`min-w-0 ${show("build")}`}>
          <div className="panel p-3 lg:sticky lg:top-20">
            <h2 className="mb-2 font-mono text-xs uppercase tracking-[0.2em] text-primary">Build tree</h2>
            <CategoryNav mission={mission} index={catalog.index} active={category} onSelect={setCategory} />
          </div>
        </aside>
        <div data-testid="architect-center" className={`min-w-0 space-y-4 ${show("spacecraft")}`}>
          <SpacecraftStage mission={mission} index={catalog.index} />
          <ImpactReport index={catalog.index} />
          <ReadinessBoard />
          <OperationsPanel mission={mission} index={catalog.index} />
          {category === "power" ? <ConceptCard id="lo3" /> : null}
          {category === "propulsion" ? <ConceptCard id="lo4" /> : null}
        </div>
        <aside aria-label="Component catalogue and inspector" data-testid="architect-right" className={`min-w-0 ${show("build")}`}>
          <ComponentCatalogue mission={mission} groups={catalog.groups} index={catalog.index} />
        </aside>
      </div>

      <section aria-label="Engineering detail" className={`space-y-4 ${show("budgets")}`}>
        <EngineeringDashboard />
        <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <div className="panel min-w-0 p-4">
            <ConstraintPanel selectedId={explainId} onExplain={explain} />
          </div>
          <div className="min-w-0 space-y-4">
            <div className="panel p-4">
              <BudgetPanel onRetry={retryAnalysis} />
            </div>
            <ConceptCard id="lo2" />
            <Counterfactual />
          </div>
        </div>
        <DetailTabs
          active={detailTab}
          onChange={setDetailTab}
          tabs={[
            { id: "explain", label: "Explanation & changes", content: <BottomDrawer explainId={explainId} index={catalog.index} /> },
            { id: "graph", label: "Traceability graph", content: <GraphExplorer /> },
            { id: "schedule", label: "Observation schedule", content: <ScheduleBoard /> },
          ]}
        />
        <PredictionPrompt missionId={mission.missionId} />
      </section>

      <ComponentChangeDialog index={catalog.index} />
      <LiveBudgetRail />
    </div>
  );
}

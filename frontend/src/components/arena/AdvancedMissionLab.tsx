"use client";

import { useState } from "react";

import { apiPost } from "@/lib/api-client";
import type { components } from "@/lib/api/schema";
import { useMissionStore } from "@/state/mission-store";

type Schemas = components["schemas"];
type MissionState = Schemas["MissionState"];

type Result =
  | { kind: "idle" }
  | { kind: "running" }
  | { kind: "ready"; title: string; body: string }
  | { kind: "error"; message: string };

function Button({
  children,
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="min-h-10 rounded-lg border border-accent-cyan/60 px-3 text-sm text-accent-cyan enabled:hover:bg-accent-cyan/10 disabled:opacity-50"
    >
      {children}
    </button>
  );
}

function output(result: Result) {
  if (result.kind === "idle") return null;
  if (result.kind === "running") return <p className="text-sm text-muted">Running backend analysis…</p>;
  if (result.kind === "error") return <p role="alert" className="text-sm text-accent-amber">{result.message}</p>;
  return (
    <div className="space-y-1 rounded-lg border border-border p-3 text-sm">
      <p className="font-medium">{result.title}</p>
      <p className="text-muted">{result.body}</p>
    </div>
  );
}

export function AdvancedMissionLab() {
  const mission = useMissionStore((s) => s.mission);
  const analysis = useMissionStore((s) => s.analysis);
  const [results, setResults] = useState<Record<string, Result>>({});

  if (!mission) return null;

  const run = async (
    key: string,
    title: string,
    request: () => Promise<{ ok: boolean; data?: unknown; error?: { message?: string } | null }>,
    summarize: (data: unknown) => string,
  ) => {
    setResults((current) => ({ ...current, [key]: { kind: "running" } }));
    const response = await request();
    if (!response.ok || response.data === undefined) {
      setResults((current) => ({
        ...current,
        [key]: { kind: "error", message: response.error?.message ?? "The backend request failed." },
      }));
      return;
    }
    setResults((current) => ({ ...current, [key]: { kind: "ready", title, body: summarize(response.data) } }));
  };

  const runTraceability = () => {
    if (!analysis) return;
    void run(
      "traceability",
      "Traceability graph ready",
      () => apiPost("/api/mission/traceability", { missionState: mission, analysis }),
      (data) => {
        const graph = (data as { graph: { nodes: unknown[]; edges: unknown[] } }).graph;
        return `${graph.nodes.length} nodes and ${graph.edges.length} deterministic edges were generated.`;
      },
    );
  };

  const runOptimization = () =>
    void run(
      "optimization",
      "Pareto frontier ready",
      () => apiPost("/api/mission/optimize", { missionState: mission, seed: mission.randomSeed, maxCandidates: 50 }),
      (data) => {
        const result = data as { paretoFrontIds: string[]; candidates: unknown[]; archetypes: Record<string, string> };
        return `${result.paretoFrontIds.length} non-dominated designs from ${result.candidates.length} candidates. Archetypes: ${Object.keys(result.archetypes).join(", ")}.`;
      },
    );

  const runRobustness = () => {
    const budget = mission.constraints.maximumBudgetUsd;
    void run(
      "robustness",
      "Robustness report ready",
      () =>
        apiPost("/api/mission/robustness", {
          missionState: mission,
          profile: {
            id: "ui-budget-sensitivity",
            version: "1",
            parameters: [
              {
                id: "budget",
                path: "constraints.maximum_budget_usd",
                kind: "epistemic",
                distribution: { kind: "uniform", min: budget * 0.9, max: budget * 1.1 },
                rationale: "UI sensitivity sweep around the selected budget.",
              },
            ],
          },
          samples: 50,
          seed: mission.randomSeed,
        }),
      (data) => {
        const result = data as { samples: number; probabilityFeasible: number; feasibilityWilson95: number[] };
        return `${result.samples} seeded samples; empirical feasibility ${(result.probabilityFeasible * 100).toFixed(1)}% (95% interval ${(result.feasibilityWilson95[0] * 100).toFixed(1)}–${(result.feasibilityWilson95[1] * 100).toFixed(1)}%).`;
      },
    );
  };

  const runBelief = () => {
    const first = mission.scienceObjectives[0]?.requiredMeasurements[0];
    if (!first) return;
    void run(
      "belief",
      "Science belief updated",
      () =>
        apiPost("/api/mission/belief/update", {
          hypotheses: [
            { id: "hypothesis-a", label: "Hypothesis A", priorProbability: 0.5, description: "Synthetic gameplay hypothesis." },
            { id: "hypothesis-b", label: "Hypothesis B", priorProbability: 0.5, description: "Synthetic gameplay hypothesis." },
          ],
          likelihood: { instrumentId: first.instrumentCapability, outcomeId: "positive", likelihoodByHypothesis: { "hypothesis-a": 0.8, "hypothesis-b": 0.2 } },
          observation: { taskId: first.id, outcomeId: "positive", timestampMissionSeconds: 0 },
        }),
      (data) => {
        const result = data as { result: { posterior: { hypotheses: { hypothesisId: string; probability: number }[] }; expectedInformationGain: number } };
        return `Posterior: ${result.result.posterior.hypotheses.map((item) => `${item.hypothesisId} ${(item.probability * 100).toFixed(0)}%`).join(", ")}. Information gain ${result.result.expectedInformationGain.toFixed(3)} bits.`;
      },
    );
  };

  const runAutonomy = () =>
    void run(
      "autonomy",
      "Onboard decision ready",
      () =>
        apiPost("/api/mission/autonomy/choose", {
          belief: {
            hypotheses: [
              { hypothesisId: "hypothesis-a", probability: 0.5 },
              { hypothesisId: "hypothesis-b", probability: 0.5 },
            ],
            observationHistory: [],
            entropyBits: 1,
            version: 0,
          },
          actions: [
            {
              id: "observe-next",
              observationId: mission.scienceObjectives[0]?.id ?? "science-objective",
              expectedScienceValue: 1,
              energyJoules: 1,
              dataBits: 1000,
              risk: 0.1,
              slewSeconds: 0,
            },
          ],
          policy: "resource-aware",
          blackout: true,
          availableEnergyJoules: 2,
          availableStorageBits: 2000,
        }),
      (data) => {
        const result = data as { decision: { selectedActionId?: string | null; decisionMaker: string; reason: string } };
        return `${result.decision.decisionMaker} selected ${result.decision.selectedActionId ?? "no action"}: ${result.decision.reason}`;
      },
    );

  const runSchedule = () => {
    const opportunities = mission.operations.observationPlan.map((item, index) => ({
      id: `observation-${index + 1}`,
      start: item.startDay * 86400,
      end: (item.startDay + item.durationHours / 24) * 86400,
      instrumentId: firstInstrument(mission, item.measurementId),
      expectedScienceValue: 1,
      generatedDataBits: 1000 * item.dutyCycle,
      energyJoules: 1,
      slewSeconds: 0,
      compatibleAttitude: "nominal",
    }));
    const contacts = mission.operations.downlinkPlan.map((item, index) => ({
      id: `contact-${index + 1}`,
      start: item.startDay * 86400,
      end: (item.startDay + item.durationMinutes / 1440) * 86400,
      maxDownlinkBits: item.durationMinutes * 60 * item.dataRateBitsPerSecond,
      stationId: "configured-ground",
      linkMarginDb: 0,
    }));
    void run(
      "schedule",
      "Operations schedule ready",
      () =>
        apiPost("/api/mission/schedule", {
          opportunities,
          contacts,
          storageCapacityBits: 100000,
          initialBufferBits: 0,
        }),
      (data) => {
        const result = data as { accepted: string[]; rejected: { id: string; reasonCode: string }[] };
        return `${result.accepted.length} observations accepted; ${result.rejected.length} rejected with explicit reason codes.`;
      },
    );
  };

  return (
    <section aria-labelledby="advanced-lab-heading" className="space-y-4 rounded-lg border border-border p-4">
      <div>
        <h2 id="advanced-lab-heading" className="text-lg font-semibold">Mission engineering lab</h2>
        <p className="text-sm text-muted">Run M09–M13 against the active mission. Results are derived by the backend and are not saved as design edits.</p>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <LabCard title="M09 Traceability" description="Build the science-to-metric dependency graph." button="Build graph" onClick={runTraceability} disabled={!analysis} result={results.traceability} />
        <LabCard title="M10 Pareto Arena" description="Generate deterministic alternatives and frontier archetypes." button="Optimize designs" onClick={runOptimization} result={results.optimization} />
        <LabCard title="M11 Robustness Lab" description="Run a seeded budget sensitivity experiment." button="Run robustness" onClick={runRobustness} result={results.robustness} />
        <LabCard title="M12 Science belief" description="Update hypotheses from a synthetic observation." button="Update belief" onClick={runBelief} result={results.belief} />
        <LabCard title="M12 Onboard autonomy" description="Choose a resource-safe action during communication blackout." button="Choose action" onClick={runAutonomy} result={results.autonomy} />
        <LabCard title="M13 Operations" description="Schedule observations and downlink contacts." button="Build schedule" onClick={runSchedule} result={results.schedule} />
      </div>
    </section>
  );
}

function LabCard({
  title,
  description,
  button,
  onClick,
  disabled,
  result,
}: {
  title: string;
  description: string;
  button: string;
  onClick: () => void;
  disabled?: boolean;
  result?: Result;
}) {
  return (
    <div className="space-y-2 rounded-lg border border-border p-3">
      <h3 className="font-medium">{title}</h3>
      <p className="text-sm text-muted">{description}</p>
      <Button onClick={onClick} disabled={disabled || result?.kind === "running"}>{button}</Button>
      {result ? output(result) : null}
    </div>
  );
}

function firstInstrument(mission: MissionState, measurementId: string): string {
  const requirement = mission.scienceObjectives
    .flatMap((objective) => objective.requiredMeasurements)
    .find((item) => item.id === measurementId);
  return requirement?.instrumentCapability ?? mission.architecture.instrumentIds[0] ?? "unknown";
}

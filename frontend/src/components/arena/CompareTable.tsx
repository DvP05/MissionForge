import { ArrowDown, ArrowUp, Equal, Minus } from "lucide-react";

import { FidelityBadge } from "@/components/common/FidelityBadge";
import { StatusPill } from "@/components/common/StatusPill";
import { MISSING } from "@/lib/format";
import type { components } from "@/lib/api/schema";
import type { MissionAnalysis } from "@/state/mission-store";
import { COMPARE_METRICS, describeDelta } from "./compare-model";

type TradeResult = components["schemas"]["TradeStudyResult"];

const LABEL = { feasible: "Feasible", marginal: "Marginal", infeasible: "Infeasible" } as const;

const ICON = { up: ArrowUp, down: ArrowDown, none: Equal, undefined: Minus } as const;

function Feasibility({ analysis, testId }: { analysis: MissionAnalysis; testId: string }) {
  return (
    <td data-testid={testId} className="space-y-1 px-3 py-2 align-top">
      <div className="font-medium">{LABEL[analysis.feasibility]}</div>
      <StatusPill tone={analysis.missionReady ? "ok" : "warn"}>
        {analysis.missionReady ? "Mission-ready" : "Not mission-ready"}
      </StatusPill>
    </td>
  );
}

function DeltaLine({
  metricKey,
  design,
  delta,
  unit,
}: {
  metricKey: string;
  design: string;
  delta: number | undefined;
  unit: string;
}) {
  const view = describeDelta(delta, unit);
  const Icon = ICON[view.direction];
  return (
    <div
      data-testid={`delta-${metricKey}-${design}`}
      data-direction={view.direction}
      className="mt-1 flex items-start gap-1.5 text-xs text-muted"
    >
      <Icon aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <span>{view.text}</span>
    </div>
  );
}

/**
 * Baseline vs alternatives. Values come from each design's analysis, deltas from the API
 * `deltas` map (alternative minus baseline). Direction is an icon plus words, never colour alone.
 */
export function CompareTable({ result, labels }: { result: TradeResult; labels: string[] }) {
  const designs: { key: string; heading: string; analysis: MissionAnalysis; deltas?: Record<string, number> }[] = [
    { key: "base", heading: "Baseline", analysis: result.baseAnalysis },
    ...result.alternatives.map((alt, i) => ({
      key: labels[i] ?? String(i),
      heading: `Alternative ${labels[i] ?? i + 1}`,
      analysis: alt.analysis,
      deltas: alt.deltas as Record<string, number>,
    })),
  ];
  return (
    <div className="overflow-x-auto rounded-lg border border-border" data-testid="compare-table-scroll">
      <table data-testid="compare-table" className="w-full min-w-[34rem] border-collapse text-left text-sm">
        <caption className="sr-only">
          Baseline and alternative designs with metric values and differences from the baseline
        </caption>
        <thead>
          <tr className="border-b border-border">
            <th scope="col" className="px-3 py-2 font-semibold">
              Metric
            </th>
            {designs.map((d) => (
              <th key={d.key} scope="col" className="px-3 py-2 font-semibold">
                {d.heading}
                {d.deltas ? <span className="block text-xs font-normal text-muted">difference vs baseline</span> : null}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr data-testid="compare-row-feasibility" className="border-b border-border">
            <th scope="row" className="px-3 py-2 align-top font-medium">
              Feasibility
            </th>
            {designs.map((d) => (
              <Feasibility key={d.key} analysis={d.analysis} testId={`compare-feasibility-${d.key}`} />
            ))}
          </tr>
          {COMPARE_METRICS.map((m) => (
            <tr key={m.key} data-testid={`compare-row-${m.key}`} className="border-b border-border last:border-b-0">
              <th scope="row" className="px-3 py-2 align-top font-medium">
                {m.label}
                <span className="block text-xs font-normal text-muted">{m.unit}</span>
              </th>
              {designs.map((d) => {
                const row = m.read(d.analysis);
                return (
                  <td key={d.key} data-testid={`compare-cell-${m.key}-${d.key}`} className="px-3 py-2 align-top">
                    {row.text === null ? (
                      <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                        <span aria-label="No value" className="font-semibold">
                          {MISSING}
                        </span>
                        <span data-testid="missing-reason" className="text-xs text-muted">
                          {row.reason ?? "The backend gave no value"}
                        </span>
                      </span>
                    ) : (
                      <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                        <span className="font-semibold tabular-nums">{row.text}</span>
                        <FidelityBadge fidelity={row.provenance.fidelity} />
                      </span>
                    )}
                    {d.deltas ? (
                      <DeltaLine metricKey={m.key} design={d.key} delta={d.deltas[m.key]} unit={m.unit} />
                    ) : null}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

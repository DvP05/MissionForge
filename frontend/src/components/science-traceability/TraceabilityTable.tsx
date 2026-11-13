import { CircleAlert, CircleCheck, CircleDashed, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

import { FidelityBadge } from "@/components/common/FidelityBadge";
import type { TraceRow, TraceStatus } from "./build-trace-rows";

const STATUS: Record<TraceStatus, { label: string; icon: ReactNode; tone: string }> = {
  uncovered: {
    label: "UNCOVERED",
    icon: <CircleAlert aria-hidden className="h-4 w-4 shrink-0" />,
    tone: "text-red-300",
  },
  "not-returned": {
    label: "Data not returned",
    icon: <TriangleAlert aria-hidden className="h-4 w-4 shrink-0" />,
    tone: "text-accent-amber",
  },
  covered: {
    label: "Covered",
    icon: <CircleCheck aria-hidden className="h-4 w-4 shrink-0" />,
    tone: "text-accent-cyan",
  },
  matched: {
    label: "Capability matched",
    icon: <CircleDashed aria-hidden className="h-4 w-4 shrink-0" />,
    tone: "text-muted",
  },
};

function statusNote(row: TraceRow, hasAnalysis: boolean): string {
  switch (row.status) {
    case "uncovered":
      return `No selected instrument has the "${row.capability}" capability (capability match).`;
    case "not-returned":
      return "Backend analysis lists this requirement as missing returned data.";
    case "covered":
      return "Backend analysis: covered for this design revision.";
    case "matched":
      return hasAnalysis
        ? "Capability match only; optional requirements are not scored as missing."
        : "Capability match only; backend analysis is pending.";
  }
}

/** Objective -> requirement -> instrument(s). Row status text is never colour alone. */
export function TraceabilityTable({
  rows,
  hasAnalysis,
}: {
  rows: readonly TraceRow[];
  hasAnalysis: boolean;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table data-testid="traceability-table" className="w-full min-w-[40rem] border-collapse text-left text-sm">
        <caption className="sr-only">
          Science traceability: each objective, its measurement requirements and the selected instruments that
          provide the capability
        </caption>
        <thead className="bg-surface text-xs uppercase tracking-wide text-muted">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">
              Objective
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Requirement
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Instrument(s)
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Status
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const s = STATUS[row.status];
            return (
              <tr
                key={row.requirementId}
                data-testid={`trace-row-${row.requirementId}`}
                data-status={row.status}
                className="border-t border-border align-top"
              >
                <td className="px-3 py-2">{row.objectiveTitle}</td>
                <td className="px-3 py-2">
                  <p>{row.requirementText}</p>
                  <p className="mt-1 text-xs text-muted">
                    <span className="font-mono">{row.capability}</span>
                    {" · "}
                    {row.required ? "required" : "optional"}
                  </p>
                </td>
                <td className="px-3 py-2">
                  {row.instruments.length > 0 ? (
                    <ul className="space-y-1">
                      {row.instruments.map((i) => (
                        <li key={i.id}>{i.name}</li>
                      ))}
                    </ul>
                  ) : (
                    <span className="text-muted">None selected</span>
                  )}
                </td>
                <td className="px-3 py-2">
                  <p
                    data-testid={`trace-status-${row.requirementId}`}
                    className={`flex items-center gap-1.5 font-medium ${s.tone}`}
                  >
                    {s.icon}
                    {s.label}
                  </p>
                  <p className="mt-1 text-xs text-muted">{statusNote(row, hasAnalysis)}</p>
                  {row.scheduled ? null : (
                    <p data-testid={`trace-unscheduled-${row.requirementId}`} className="mt-1 text-xs text-accent-amber">
                      No observation scheduled
                    </p>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function WeightsNote() {
  return (
    <p className="flex flex-wrap items-center gap-2 text-xs text-muted">
      <FidelityBadge fidelity="gameplay-estimate" />
      Objective priorities and coverage weights are scenario design choices, not measurements.
    </p>
  );
}

import { Loader2, TriangleAlert } from "lucide-react";

import { StatusPill } from "@/components/common/StatusPill";
import { ACTION_CLASS } from "@/components/common/States";
import type { AnalysisStatus as Status, MissionAnalysis } from "@/state/mission-store";

/** Which revision the numbers belong to, whether they are updating, stale or failed. */
export function AnalysisStatus({
  analysis,
  status,
  designRevision,
  onRetry,
}: {
  analysis: MissionAnalysis | null;
  status: Status;
  designRevision: number;
  onRetry: () => void;
}) {
  const behind = analysis !== null && analysis.designRevision !== designRevision;
  const failed = status === "error";
  return (
    <div className="space-y-2" data-testid="analysis-status">
      <div className="flex flex-wrap items-center gap-2">
        <span data-testid="analysis-revision" className="text-xs text-muted">
          {analysis ? `Analysis for revision ${analysis.designRevision}` : "No analysis yet"}
        </span>
        {status === "calculating" ? (
          <span role="status">
            <StatusPill
              tone="info"
              icon={<Loader2 aria-hidden className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" />}
            >
              Updating
            </StatusPill>
          </span>
        ) : null}
        {analysis && (failed || (behind && status !== "calculating")) ? (
          <span data-testid="stale-badge">
            <StatusPill tone="warn" icon={<TriangleAlert aria-hidden className="h-3.5 w-3.5" />}>
              {behind
                ? `Stale: showing revision ${analysis.designRevision}, design is at ${designRevision}`
                : "Analysis failed — showing last result"}
            </StatusPill>
          </span>
        ) : null}
      </div>
      {failed ? (
        <div
          data-testid="analysis-failed"
          role="alert"
          className="flex flex-wrap items-center gap-3 rounded-lg border border-accent-amber/60 p-3 text-sm"
        >
          <span>
            Analysis failed — retry.{" "}
            {analysis ? "The last good numbers are shown below, marked stale." : "No earlier numbers exist."}
          </span>
          <button type="button" onClick={onRetry} className={ACTION_CLASS}>
            Retry
          </button>
        </div>
      ) : null}
    </div>
  );
}

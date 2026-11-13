import { FidelityBadge } from "@/components/common/FidelityBadge";
import { ProvenancePopover } from "@/components/common/ProvenancePopover";
import type { components } from "@/lib/api/schema";
import { MISSING } from "@/lib/format";

type Provenance = components["schemas"]["Provenance"];

/**
 * One labelled number with its fidelity badge and provenance popover. A missing value
 * renders a dash and a reason, never 0.
 */
export function Metric({
  label,
  text,
  provenance,
  reason,
  was,
  testId,
}: {
  label: string;
  text: string | null;
  provenance: Provenance;
  /** Why there is no number (shown when text is null). */
  reason: string;
  /** Previous value, shown when the tile changed. */
  was?: string | null;
  testId?: string;
}) {
  return (
    <div className="space-y-1" data-testid={testId}>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {text === null ? (
          <>
            <span className="text-lg font-semibold" aria-label="No value">
              {MISSING}
            </span>
            {reason ? (
              <span data-testid="missing-reason" className="text-xs text-muted">
                {reason}
              </span>
            ) : null}
          </>
        ) : (
          <>
            <span className="text-lg font-semibold tabular-nums">{text}</span>
            <FidelityBadge fidelity={provenance.fidelity} />
            <ProvenancePopover provenance={provenance} label={label} />
            {was ? <span className="text-xs text-muted">was {was}</span> : null}
          </>
        )}
      </dd>
    </div>
  );
}

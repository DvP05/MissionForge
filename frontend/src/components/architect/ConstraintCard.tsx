import { ConstraintBadge } from "@/components/common/ConstraintBadge";
import { FidelityBadge } from "@/components/common/FidelityBadge";
import { ProvenancePopover } from "@/components/common/ProvenancePopover";
import type { components } from "@/lib/api/schema";
import { formatFraction, formatQuantity, MISSING } from "@/lib/format";

export type Constraint = components["schemas"]["ConstraintResult"];
type Quantity = components["schemas"]["Quantity"];

function QuantityLine({
  testId,
  label,
  quantity,
  reason,
}: {
  testId: string;
  label: string;
  quantity: Quantity | null | undefined;
  reason: string;
}) {
  const text = formatQuantity(quantity);
  return (
    <div className="space-y-0.5">
      <dt className="text-xs text-muted">{label}</dt>
      <dd data-testid={testId} className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
        {text === MISSING || !quantity ? (
          <>
            <span aria-label="No value">{MISSING}</span>
            <span data-testid="missing-reason" className="text-xs text-muted">
              {reason}
            </span>
          </>
        ) : (
          <>
            <span className="font-medium tabular-nums">{text}</span>
            <FidelityBadge fidelity={quantity.provenance.fidelity} />
            <ProvenancePopover provenance={quantity.provenance} label={label} />
          </>
        )}
      </dd>
    </div>
  );
}

/** One backend constraint result. Not-modelled is styled and worded differently from pass. */
export function ConstraintCard({
  constraint,
  selected,
  onExplain,
}: {
  constraint: Constraint;
  selected: boolean;
  onExplain: (id: string) => void;
}) {
  const notModelled = constraint.status === "not-modelled";
  const missingReason = notModelled
    ? "Not modelled: no numeric conclusion is claimed"
    : "The backend did not report this value";
  return (
    <li
      data-testid={`constraint-card-${constraint.id}`}
      data-status={constraint.status}
      className={`space-y-3 rounded-lg border p-3 ${
        notModelled ? "border-dashed border-border" : "border-border"
      } ${selected ? "ring-2 ring-accent-cyan/60" : ""}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{constraint.label}</h3>
        <ConstraintBadge status={constraint.status} />
      </div>
      {notModelled ? (
        <p className="text-xs text-muted">
          Not modelled: the data or model is insufficient for a reliable conclusion, so this check is
          neither passed nor failed.
        </p>
      ) : null}
      <dl className="grid gap-2 sm:grid-cols-2">
        <QuantityLine testId="constraint-actual" label="Actual" quantity={constraint.actual} reason={missingReason} />
        <QuantityLine testId="constraint-limit" label="Limit" quantity={constraint.limit} reason={missingReason} />
        <div className="space-y-0.5">
          <dt className="text-xs text-muted">Margin</dt>
          <dd data-testid="constraint-margin" className="text-sm font-medium tabular-nums">
            {constraint.marginFraction === null || constraint.marginFraction === undefined ? (
              <span className="font-normal text-muted">{MISSING} no margin reported</span>
            ) : (
              formatFraction(constraint.marginFraction)
            )}
          </dd>
        </div>
        <div className="space-y-0.5">
          <dt className="text-xs text-muted">Impacted subsystems</dt>
          <dd data-testid="constraint-impacted" className="text-sm">
            {constraint.impactedSubsystems && constraint.impactedSubsystems.length > 0
              ? constraint.impactedSubsystems.join(", ")
              : `${MISSING} none named`}
          </dd>
        </div>
      </dl>
      {constraint.status === "fail" || constraint.status === "warning" ? (
        <div className="space-y-1">
          <p className="text-xs text-muted">Suggested actions</p>
          {constraint.suggestedActions && constraint.suggestedActions.length > 0 ? (
            <ul className="space-y-1 text-sm">
              {constraint.suggestedActions.map((a) => (
                <li key={a.actionId} data-testid="constraint-action">
                  <span className="font-medium">{a.label}</span>
                  <span className="text-muted"> — {a.expectedEffect}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">The backend suggested no action for this result.</p>
          )}
        </div>
      ) : null}
      <p data-testid="constraint-explanation" className="text-xs text-muted">
        {constraint.explanation}
      </p>
      <button
        type="button"
        onClick={() => onExplain(constraint.id)}
        aria-label={`Explain ${constraint.label}`}
        aria-pressed={selected}
        className="inline-flex min-h-11 items-center rounded-lg border border-border px-3 text-sm hover:text-accent-cyan"
      >
        Explain
      </button>
    </li>
  );
}

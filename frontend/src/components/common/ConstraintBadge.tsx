import { CircleCheck, CircleSlash, CircleX, TriangleAlert, type LucideIcon } from "lucide-react";

import type { components } from "@/lib/api/schema";

export type ConstraintStatus = components["schemas"]["ConstraintResult"]["status"];

const CONFIG: Record<ConstraintStatus, { label: string; Icon: LucideIcon; tone: string }> = {
  pass: { label: "Pass", Icon: CircleCheck, tone: "border-accent-green/50 text-accent-green" },
  warning: { label: "Watch", Icon: TriangleAlert, tone: "border-accent-amber/60 text-accent-amber" },
  fail: { label: "Fail", Icon: CircleX, tone: "border-accent-red/60 text-accent-red" },
  "not-modelled": { label: "Not modelled", Icon: CircleSlash, tone: "border-border text-muted" },
};

/** Constraint outcome. Icon shape AND text carry the meaning, never colour alone. */
export function ConstraintBadge({ status }: { status: ConstraintStatus }) {
  const { label, Icon, tone } = CONFIG[status];
  return (
    <span
      data-testid={`constraint-badge-${status}`}
      data-status={status}
      className={`inline-flex items-center gap-1.5 border bg-[#232729]/80 px-2 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-wider ${tone}`}
    >
      <Icon aria-hidden className="h-3.5 w-3.5 shrink-0" />
      {label}
    </span>
  );
}

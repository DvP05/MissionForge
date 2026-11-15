import { BadgeCheck, Calculator, CircleSlash, FlaskConical, type LucideIcon } from "lucide-react";

import type { components } from "@/lib/api/schema";

export type Fidelity = components["schemas"]["Provenance"]["fidelity"];

const CONFIG: Record<Fidelity, { label: string; Icon: LucideIcon; tone: string }> = {
  "source-backed": { label: "Source-backed", Icon: BadgeCheck, tone: "border-accent-cyan/50 text-accent-cyan" },
  derived: { label: "Derived", Icon: Calculator, tone: "border-foreground/40 text-foreground" },
  "gameplay-estimate": { label: "Gameplay estimate", Icon: FlaskConical, tone: "border-accent-amber/60 text-accent-amber" },
  "not-modelled": { label: "Not modelled", Icon: CircleSlash, tone: "border-border text-muted" },
};

/** How trustworthy a number is. Icon and text, never colour alone. */
export function FidelityBadge({ fidelity }: { fidelity: Fidelity }) {
  const { label, Icon, tone } = CONFIG[fidelity];
  return (
    <span
      data-testid={`fidelity-badge-${fidelity}`}
      data-fidelity={fidelity}
      className={`inline-flex items-center gap-1.5 border bg-[#232729]/80 px-2 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-wider ${tone}`}
    >
      <Icon aria-hidden className="h-3.5 w-3.5 shrink-0" />
      {label}
    </span>
  );
}

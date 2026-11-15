import type { ReactNode } from "react";

export type PillTone = "neutral" | "info" | "ok" | "warn" | "danger";

const TONES: Record<PillTone, string> = {
  neutral: "border-border text-muted",
  info: "border-accent-cyan/50 text-accent-cyan",
  ok: "border-accent-green/50 text-accent-green",
  warn: "border-accent-amber/60 text-accent-amber",
  danger: "border-accent-red/60 text-accent-red",
};

/** Small text label. Meaning is always in the text; tone only reinforces it. */
export function StatusPill({
  tone = "neutral",
  icon,
  children,
  testId,
}: {
  tone?: PillTone;
  icon?: ReactNode;
  children: ReactNode;
  testId?: string;
}) {
  return (
    <span
      data-testid={testId}
      className={`inline-flex items-center gap-1.5 border bg-[#232729]/80 px-2 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-wider ${TONES[tone]}`}
    >
      {icon}
      {children}
    </span>
  );
}

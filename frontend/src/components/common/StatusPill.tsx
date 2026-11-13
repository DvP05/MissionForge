import type { ReactNode } from "react";

export type PillTone = "neutral" | "info" | "ok" | "warn" | "danger";

const TONES: Record<PillTone, string> = {
  neutral: "border-border text-muted",
  info: "border-accent-cyan/50 text-accent-cyan",
  ok: "border-accent-cyan/50 text-accent-cyan",
  warn: "border-accent-amber/60 text-accent-amber",
  danger: "border-red-400/60 text-red-300",
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
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONES[tone]}`}
    >
      {icon}
      {children}
    </span>
  );
}

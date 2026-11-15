import { STATUS_TONE, type EngStatus } from "@/lib/spacecraft/engineering-status";

/** Text status chip (the word carries the meaning; colour only reinforces it). */
export function EngStatusChip({ status, testId }: { status: EngStatus; testId?: string }) {
  return (
    <span
      data-testid={testId}
      data-status={status}
      className={`inline-flex items-center rounded border px-1.5 py-px font-mono text-[10px] font-semibold tracking-wider ${STATUS_TONE[status]}`}
    >
      {status}
    </span>
  );
}

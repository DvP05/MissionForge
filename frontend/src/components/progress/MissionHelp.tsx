import { CircleHelp } from "lucide-react";

/** Short contextual help (design_update.md 5.2): the loop in five lines, keyboard reachable. */
export function MissionHelp() {
  return (
    <details className="relative">
      <summary className="btn btn-tertiary min-h-9 list-none px-2.5 text-xs" data-testid="help-toggle">
        <CircleHelp aria-hidden className="h-4 w-4" /> How to play
      </summary>
      <div className="panel absolute right-0 z-40 mt-2 w-[min(22rem,calc(100vw-2rem))] space-y-2 p-4 text-sm">
        <p className="font-semibold">Design a mission. Make the trade-offs. Fly the consequences.</p>
        <ol className="list-decimal space-y-1 pl-5 text-muted">
          <li>Read the brief and keep 2–4 science objectives.</li>
          <li>In the architect, pick a subsystem on the left, then Add, Replace or Remove parts on the right.</li>
          <li>Every confirmed change is a new design revision; the engine re-analyses it and the impact report shows what moved.</li>
          <li>Clear every FAIL gate. A high score never hides a hard failure.</li>
          <li>Launch, make the operational calls, then read the debrief.</li>
        </ol>
        <p className="text-xs text-muted">All numbers come from the Python engine. Catalogue values are illustrative gameplay estimates.</p>
      </div>
    </details>
  );
}

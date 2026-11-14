import { useState } from "react";
import { FastForward, Pause, Play, SkipForward, StepForward } from "lucide-react";

import { SPEEDS } from "./playback";
import type { Playback } from "./usePlayback";

const BTN =
  "inline-flex min-h-11 items-center gap-2 rounded-lg border border-border px-3 text-sm hover:text-accent-cyan disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:text-inherit";

/** Display pacing only; speed never changes the run. */
export function PlaybackControls({ pb }: { pb: Playback }) {
  const [confirming, setConfirming] = useState(false);
  const n = pb.undecidedAhead;
  const requestSkip = () => (n > 0 ? setConfirming(true) : pb.skipToEnd());
  return (
    <section aria-label="Playback controls" className="flex flex-wrap items-center gap-2">
      {pb.reducedMotion ? (
        <p data-testid="reduced-motion-note" className="w-full text-xs text-muted">
          Reduced motion is on: auto-play is off. Use the step controls.
        </p>
      ) : (
        <button
          type="button"
          data-testid="playback-play"
          onClick={pb.playing ? pb.pause : pb.play}
          disabled={!pb.playing && !!pb.pending}
          title={pb.pending ? "Choose an option on the decision card first" : undefined}
          className={BTN}
        >
          {pb.playing ? <Pause aria-hidden className="h-4 w-4" /> : <Play aria-hidden className="h-4 w-4" />}
          {pb.playing ? "Pause" : pb.atEnd ? "Replay" : "Play"}
        </button>
      )}
      <button type="button" data-testid="step-event" onClick={pb.step} disabled={!pb.hasNextEvent} className={BTN}>
        <StepForward aria-hidden className="h-4 w-4" />
        Step to next event
      </button>
      <button
        type="button"
        data-testid="skip-next-decision"
        onClick={pb.skipToNextDecision}
        disabled={!pb.hasNextDecision}
        className={BTN}
      >
        <SkipForward aria-hidden className="h-4 w-4" />
        Skip to next decision
      </button>
      <button type="button" data-testid="skip-to-end" onClick={requestSkip} disabled={!!pb.pending || pb.atEnd}
        title={pb.pending ? "Make the pending decision first" : undefined} className={BTN}>
        <FastForward aria-hidden className="h-4 w-4" />
        Skip to end
      </button>
      {pb.reducedMotion ? null : (
        <div role="group" aria-label="Playback speed" className="flex items-center gap-1">
          {SPEEDS.map((s) => (
            <button
              key={s}
              type="button"
              data-testid={`speed-${s}`}
              aria-pressed={pb.speed === s}
              onClick={() => pb.setSpeed(s)}
              className={`${BTN} ${pb.speed === s ? "border-accent-cyan/60 bg-accent-cyan/10 text-accent-cyan" : ""}`}
            >
              {s}×
            </button>
          ))}
        </div>
      )}
      {confirming && n > 0 ? (
        <div data-testid="skip-end-confirm" role="alertdialog" aria-label="Confirm skip to end" className="w-full space-y-2 rounded-lg border border-accent-amber/60 p-3 text-sm">
          <p>
            Skipping to the end means {n} undecided {n === 1 ? "decision" : "decisions"} will use ground defaults.
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              data-testid="skip-end-confirm-yes"
              onClick={() => {
                setConfirming(false);
                pb.skipToEnd();
              }}
              className={BTN}
            >
              Skip and use ground defaults
            </button>
            <button type="button" data-testid="skip-end-cancel" onClick={() => setConfirming(false)} className={BTN}>
              Keep playing
            </button>
          </div>
        </div>
      ) : null}
      <p className="w-full text-xs text-muted">Speed changes display pacing only; the run itself is fixed.</p>
    </section>
  );
}

"use client";

import { formatFraction } from "@/lib/format";
import { useLocalValue } from "@/lib/learning/useLocalValue";

/** Prediction bands for "how much collected science will reach Earth?" (LO-5). */
const BANDS = [
  { id: "low", label: "Under a quarter", lo: 0, hi: 0.25 },
  { id: "mid", label: "A quarter to three quarters", lo: 0.25, hi: 0.75 },
  { id: "high", label: "Over three quarters", lo: 0.75, hi: 1.0001 },
] as const;

const key = (missionId: string) => `missionforge:prediction:return:${missionId}`;

/** Optional prediction before launch (architect). Not required to launch. */
export function PredictionPrompt({ missionId }: { missionId: string }) {
  const [value, setValue] = useLocalValue(key(missionId));
  return (
    <fieldset data-testid="prediction-prompt" className="space-y-1 rounded-xl border border-border p-3">
      <legend className="px-1 text-sm font-medium">
        Optional prediction: how much of the science you collect will reach Earth?
      </legend>
      <div className="flex flex-wrap gap-x-4">
        {BANDS.map((b) => (
          <label key={b.id} className="flex min-h-11 cursor-pointer items-center gap-2 text-sm">
            <input
              type="radio"
              name={`prediction-${missionId}`}
              value={b.id}
              checked={value === b.id}
              onChange={() => setValue(b.id)}
              className="h-4 w-4 accent-cyan-400"
            />
            {b.label}
          </label>
        ))}
      </div>
      <p className="text-xs text-muted">Saved in this browser only; the review compares it with the flown result.</p>
    </fieldset>
  );
}

/** Review: the player's prediction against the run's returned fraction of collected science. */
export function PredictionResult({ missionId, collected, returned }: { missionId: string; collected: number; returned: number }) {
  const [value] = useLocalValue(key(missionId));
  const band = BANDS.find((b) => b.id === value);
  if (!band) return null;
  const share = collected > 0 ? returned / collected : 0;
  const hit = share >= band.lo && share < band.hi;
  return (
    <p data-testid="prediction-result" className="text-sm">
      You predicted &ldquo;{band.label.toLowerCase()}&rdquo; of the collected science would reach Earth. The flown
      mission returned {formatFraction(Math.min(1, share))} of what it collected: {hit ? "your prediction held." : "the result differed; the data path explains why."}
    </p>
  );
}

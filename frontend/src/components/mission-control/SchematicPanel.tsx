import { PHASE_LABEL, type Phase } from "./playback";

/** Simple 2D fallback view. No WebGL is used; the drawing is illustrative, not to scale. */
export function SchematicPanel({ phase, day }: { phase: Phase | null; day: number }) {
  return (
    <section
      data-testid="schematic-2d"
      aria-label="2D mission schematic"
      className="space-y-2 rounded-lg border border-border p-3"
    >
      <h2 className="text-sm font-semibold">Mission schematic (2D)</h2>
      <svg
        viewBox="0 0 320 120"
        role="img"
        aria-label={`Illustrative schematic: Earth, spacecraft and target. Current phase ${phase ? PHASE_LABEL[phase] : "not started"}.`}
        className="h-auto w-full"
      >
        <circle cx="30" cy="60" r="16" fill="none" stroke="#22d3ee" strokeWidth="2" />
        <circle cx="285" cy="60" r="8" fill="none" stroke="#8fa0b8" strokeWidth="2" />
        <path d="M46 60 Q160 10 277 60" fill="none" stroke="#243044" strokeWidth="2" strokeDasharray="4 4" />
        <rect x="150" y="26" width="14" height="10" fill="#fbbf24" />
        <text x="30" y="96" textAnchor="middle" fontSize="10" fill="#8fa0b8">Earth</text>
        <text x="285" y="84" textAnchor="middle" fontSize="10" fill="#8fa0b8">Target</text>
        <text x="157" y="20" textAnchor="middle" fontSize="10" fill="#8fa0b8">Spacecraft</text>
      </svg>
      <p className="text-xs text-muted">
        Illustrative only: not to scale and not a trajectory. Position is not computed; the phase and day shown
        come from the run (phase: {phase ? PHASE_LABEL[phase] : "not started"}, day {day.toFixed(1)}).
      </p>
    </section>
  );
}

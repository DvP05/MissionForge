import { formatNumber } from "@/lib/format";
import { PHASE_LABEL, type MissionRun, type Phase } from "./playback";

/**
 * 2D mission map (Task 7.2, M05). Driven only by run data: the destination type picks the
 * picture (transfer arc, Earth-Moon arc, or Earth orbit), phase markers sit at the run's
 * phase-transition days, and the spacecraft marker at the playback day. Geometry is
 * illustrative and not to scale; nothing here computes a position. No animation is used,
 * so reduced-motion needs no special case.
 */
const W = 320;
const H = 140;

type Point = { x: number; y: number };

function arcPoint(t: number): Point {
  // quadratic Bezier from Earth (46, 80) to target (274, 80) via (160, 10)
  const u = Math.min(1, Math.max(0, t));
  const x = (1 - u) * (1 - u) * 46 + 2 * (1 - u) * u * 160 + u * u * 274;
  const y = (1 - u) * (1 - u) * 80 + 2 * (1 - u) * u * 10 + u * u * 80;
  return { x, y };
}

function orbitPoint(t: number): Point {
  const a = t * 2 * Math.PI * 6 - Math.PI / 2; // a few illustrative laps over the mission
  return { x: 160 + 52 * Math.cos(a), y: 72 + 52 * Math.sin(a) };
}

export function SchematicPanel({ run, phase, day }: { run: MissionRun; phase: Phase | null; day: number }) {
  const snap = run.inputSnapshot;
  const traj = snap.trajectory;
  const orbit = snap.destination.bodyType === "planet"; // Earth orbit scenarios
  const duration = Math.max(snap.operations.missionDurationDays, 1);
  const tof = traj.timeOfFlightDays ?? 0;
  // transfer progress until arrival, then the spacecraft stays at the target
  const progress = (d: number) => (orbit ? d / duration : tof > 0 ? d / tof : 1);
  const at = (d: number) => (orbit ? orbitPoint(progress(d)) : arcPoint(progress(d)));
  const here = at(day);
  const markers = run.phaseTransitions.filter((t) => !orbit && t.missionDay <= tof && t.missionDay > 0);
  const target = snap.destination.name;
  const facts = [
    `provider ${traj.provider}`,
    tof > 0 ? `time of flight ${formatNumber(tof)} d` : null,
    traj.c3Km2PerS2 != null ? `C3 ${formatNumber(traj.c3Km2PerS2)} km²/s²` : null,
    traj.missionDeltaVKmPerS != null ? `spacecraft delta-v ${formatNumber(traj.missionDeltaVKmPerS)} km/s` : null,
  ].filter(Boolean);
  const where = orbit
    ? `in low Earth orbit, day ${formatNumber(day)} of ${formatNumber(duration)}`
    : day < tof
      ? `in transfer, ${Math.round(progress(day) * 100)}% of the ${formatNumber(tof)}-day flight`
      : `at ${target}`;

  return (
    <section data-testid="schematic-2d" aria-label="2D mission map" className="space-y-2 rounded-lg border border-border p-3">
      <h2 className="text-sm font-semibold">Mission map (2D)</h2>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-labelledby="mission-map-desc" className="h-auto w-full">
        <desc id="mission-map-desc">
          Illustrative map, not to scale. Spacecraft {where}. Current phase {phase ? PHASE_LABEL[phase] : "not started"}.
        </desc>
        {orbit ? (
          <>
            <circle cx="160" cy="72" r="22" fill="none" stroke="#22d3ee" strokeWidth="2" />
            <circle cx="160" cy="72" r="52" fill="none" stroke="#243044" strokeWidth="2" strokeDasharray="4 4" />
            <text x="160" y="76" textAnchor="middle" fontSize="10" fill="#8fa0b8">Earth</text>
          </>
        ) : (
          <>
            <circle cx="30" cy="80" r="16" fill="none" stroke="#22d3ee" strokeWidth="2" />
            <circle cx="285" cy="80" r={snap.destination.bodyType === "moon" ? 10 : 6} fill="none" stroke="#8fa0b8" strokeWidth="2" />
            <path d="M46 80 Q160 10 274 80" fill="none" stroke="#243044" strokeWidth="2" strokeDasharray="4 4" />
            <text x="30" y="114" textAnchor="middle" fontSize="10" fill="#8fa0b8">Earth</text>
            <text x="285" y="104" textAnchor="middle" fontSize="10" fill="#8fa0b8">
              {snap.destination.bodyType === "moon" ? "Moon" : "Target"}
            </text>
            {markers.map((t) => {
              const p = arcPoint(t.missionDay / tof);
              return (
                <g key={`${t.phase}-${t.missionDay}`} data-testid="map-phase-marker">
                  <circle cx={p.x} cy={p.y} r="2.5" fill="#8fa0b8" />
                  <title>
                    {PHASE_LABEL[t.phase]} from day {formatNumber(t.missionDay)}
                  </title>
                </g>
              );
            })}
          </>
        )}
        <rect data-testid="map-spacecraft" x={here.x - 6} y={here.y - 4} width="12" height="8" fill="#fbbf24" />
      </svg>
      <p data-testid="mission-map-text" className="text-xs">
        Spacecraft {where}. Phase: {phase ? PHASE_LABEL[phase] : "not started"}.
      </p>
      <p className="text-xs text-muted">
        Illustrative geometry, not to scale: the marker shows progress through the run&apos;s timeline, not a computed
        position. Trajectory data: {facts.join(", ")}.
      </p>
    </section>
  );
}

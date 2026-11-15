import type { ScenarioId } from "@/state/mission-store";

/**
 * Decorative destination art per scenario (SVG, no images, no network). Illustrative only:
 * nothing here is to scale or derived from data.
 */
export function DestinationGlyph({ scenarioId, className = "" }: { scenarioId: ScenarioId; className?: string }) {
  const id = `g-${scenarioId}`;
  return (
    <svg viewBox="0 0 320 120" aria-hidden className={className} preserveAspectRatio="xMidYMid slice">
      <defs>
        <radialGradient id={`${id}-earth`} cx="35%" cy="35%" r="70%">
          <stop offset="0%" stopColor="#7fd3ff" />
          <stop offset="45%" stopColor="#2a6fd6" />
          <stop offset="100%" stopColor="#0a1a3a" />
        </radialGradient>
        <radialGradient id={`${id}-moon`} cx="35%" cy="30%" r="75%">
          <stop offset="0%" stopColor="#e6e9ef" />
          <stop offset="55%" stopColor="#8f97a6" />
          <stop offset="100%" stopColor="#1d2230" />
        </radialGradient>
        <radialGradient id={`${id}-rock`} cx="40%" cy="35%" r="70%">
          <stop offset="0%" stopColor="#c9a27a" />
          <stop offset="60%" stopColor="#6b513c" />
          <stop offset="100%" stopColor="#1e1712" />
        </radialGradient>
        <linearGradient id={`${id}-sky`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#0b1220" />
          <stop offset="100%" stopColor="#161033" />
        </linearGradient>
      </defs>
      <rect width="320" height="120" fill={`url(#${id}-sky)`} />
      {[
        [20, 18], [64, 92], [110, 30], [150, 100], [200, 14], [240, 70], [290, 24], [300, 104], [45, 55],
      ].map(([x, y]) => (
        <circle key={`${x}-${y}`} cx={x} cy={y} r="0.9" fill="#dfe9ff" opacity="0.8" />
      ))}
      {scenarioId === "earth-observation" ? (
        <>
          <circle cx="250" cy="150" r="110" fill={`url(#${id}-earth)`} />
          <circle cx="250" cy="150" r="114" fill="none" stroke="#7fd3ff" strokeOpacity="0.35" strokeWidth="3" />
          <ellipse cx="250" cy="150" rx="150" ry="58" fill="none" stroke="#35d8f2" strokeOpacity="0.45" strokeDasharray="3 5" />
          <circle cx="112" cy="122" r="3" fill="#35d8f2" />
        </>
      ) : scenarioId === "lunar-polar-scout" ? (
        <>
          <circle cx="245" cy="70" r="62" fill={`url(#${id}-moon)`} />
          <path d="M183 70 A62 62 0 0 0 307 70 L307 132 L183 132 Z" fill="#070b14" opacity="0.55" />
          {[
            [228, 52, 8], [262, 84, 6], [240, 96, 4], [270, 46, 5],
          ].map(([x, y, r]) => (
            <circle key={`${x}`} cx={x} cy={y} r={r} fill="#5d6574" opacity="0.6" />
          ))}
          <ellipse cx="245" cy="70" rx="92" ry="22" fill="none" stroke="#9b7cff" strokeOpacity="0.5" strokeDasharray="3 5" transform="rotate(-70 245 70)" />
        </>
      ) : (
        <>
          <path
            d="M230 40 q30 -18 52 2 q22 18 6 42 q-12 22 -42 18 q-34 -2 -40 -28 q-4 -24 24 -34z"
            fill={`url(#${id}-rock)`}
          />
          <circle cx="252" cy="58" r="5" fill="#3b2c20" opacity="0.6" />
          <circle cx="270" cy="76" r="3.5" fill="#3b2c20" opacity="0.6" />
          <path d="M20 110 Q140 10 238 60" fill="none" stroke="#ffb547" strokeOpacity="0.55" strokeDasharray="3 5" />
          <circle cx="20" cy="110" r="3" fill="#4d8dff" />
        </>
      )}
    </svg>
  );
}

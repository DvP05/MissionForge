"use client";

import { useState } from "react";

import type { components } from "@/lib/api/schema";

type MissionState = components["schemas"]["MissionState"];
type Phase = components["schemas"]["MissionRun"]["phases"][number];

const PHASE_PROGRESS: Partial<Record<Phase, number>> = {
  "pre-launch": 0.05,
  "launch-deployment": 0.15,
  commissioning: 0.22,
  cruise: 0.45,
  "mid-course": 0.62,
  approach: 0.8,
  "science-ops": 0.9,
  "downlink-return": 0.97,
  complete: 1,
  terminated: 0.5,
};

const PHASE_LABEL: Record<Phase, string> = {
  "pre-launch": "Pre-launch",
  "launch-deployment": "Launch and deployment",
  commissioning: "Commissioning",
  cruise: "Cruise",
  "mid-course": "Mid-course",
  approach: "Approach",
  "science-ops": "Science operations",
  "downlink-return": "Downlink return",
  complete: "Complete",
  terminated: "Terminated",
};

function phaseLabel(phase: Phase | null): string {
  return phase ? PHASE_LABEL[phase] : "Not started";
}

function markerPosition(progress: number): { x: number; y: number } {
  const clamped = Math.max(0, Math.min(1, progress));
  return {
    x: 70 + 180 * clamped,
    y: 82 - 42 * Math.sin(Math.PI * clamped),
  };
}

function threeDimensionalMarker(progress: number): { x: number; y: number; z: number } {
  const clamped = Math.max(0, Math.min(1, progress));
  return {
    x: -38 + 76 * clamped,
    y: -18 - 24 * Math.sin(Math.PI * clamped),
    z: 12 * Math.sin(Math.PI * clamped),
  };
}

export function MissionVisualization({
  mission,
  phase = null,
  day,
}: {
  mission: MissionState;
  phase?: Phase | null;
  day?: number;
}) {
  const [viewMode, setViewMode] = useState<"2d" | "3d">("2d");
  const progress = phase ? PHASE_PROGRESS[phase] ?? 0 : 0;
  const marker = markerPosition(progress);
  const marker3d = threeDimensionalMarker(progress);
  const targetLabel = mission.destination.name || mission.destination.bodyId;
  const trajectoryLabel = mission.trajectory.optionId;
  const providerLabel = mission.trajectory.provider.replaceAll("-", " ");

  return (
    <section
      data-testid="schematic-2d"
      aria-labelledby="mission-visualization-heading"
      className="space-y-3 rounded-lg border border-border p-3"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 id="mission-visualization-heading" className="text-sm font-semibold">
            Mission trajectory
          </h2>
          <span className="text-xs text-muted">Illustrative scale</span>
        </div>
        <div className="flex rounded-md border border-border p-0.5" aria-label="Visualization mode">
          <button
            type="button"
            aria-pressed={viewMode === "2d"}
            onClick={() => setViewMode("2d")}
            className="rounded px-2 py-1 text-xs font-medium aria-pressed:bg-cyan-400/15 aria-pressed:text-cyan-200"
          >
            2D
          </button>
          <button
            type="button"
            aria-pressed={viewMode === "3d"}
            onClick={() => setViewMode("3d")}
            className="rounded px-2 py-1 text-xs font-medium aria-pressed:bg-cyan-400/15 aria-pressed:text-cyan-200"
          >
            3D
          </button>
        </div>
      </div>
      {viewMode === "2d" ? (
        <svg
          viewBox="0 0 320 140"
          role="img"
          aria-labelledby="mission-visualization-title mission-visualization-description"
          className="h-auto w-full"
        >
          <title id="mission-visualization-title">
            {mission.scenarioId} trajectory from Earth to {targetLabel}
          </title>
          <desc id="mission-visualization-description">
            A stylized transfer path for the selected trajectory. It is not a propagated ephemeris.
          </desc>
          <defs>
            <linearGradient id="mission-transfer-gradient" x1="0%" x2="100%">
              <stop offset="0%" stopColor="#22d3ee" />
              <stop offset="100%" stopColor="#fbbf24" />
            </linearGradient>
          </defs>
          <circle cx="36" cy="82" r="22" fill="none" stroke="#22d3ee" strokeWidth="2" />
          <circle cx="36" cy="82" r="8" fill="#22d3ee" fillOpacity="0.18" stroke="#22d3ee" />
          <path
            d="M58 82 C105 18 204 18 274 82"
            fill="none"
            stroke="#334155"
            strokeDasharray="4 4"
            strokeWidth="2"
          />
          <path
            d="M58 82 C105 18 204 18 274 82"
            fill="none"
            stroke="url(#mission-transfer-gradient)"
            strokeDasharray="6 8"
            strokeWidth="2"
          />
          <circle cx="274" cy="82" r="13" fill="none" stroke="#fbbf24" strokeWidth="2" />
          <circle cx={marker.x} cy={marker.y} r="5" fill="#fbbf24" stroke="#fff" strokeWidth="1.5" />
          <text x="36" y="122" textAnchor="middle" fontSize="10" fill="#8fa0b8">
            Earth
          </text>
          <text x="274" y="122" textAnchor="middle" fontSize="10" fill="#8fa0b8">
            {targetLabel}
          </text>
          <text x={marker.x} y={marker.y - 10} textAnchor="middle" fontSize="9" fill="#fbbf24">
            Spacecraft
          </text>
        </svg>
      ) : (
        <div
          data-testid="schematic-3d"
          role="img"
          aria-label={`${mission.scenarioId} three-dimensional illustrative trajectory from Earth to ${targetLabel}`}
          className="relative h-56 overflow-hidden rounded-md border border-slate-800 bg-[radial-gradient(circle_at_center,_#172554,_#020617_70%)]"
          style={{ perspective: "700px" }}
        >
          <div
            className="absolute inset-8"
            style={{ transform: "rotateX(58deg) rotateZ(-12deg)", transformStyle: "preserve-3d" }}
          >
            <div className="absolute left-1/2 top-1/2 h-36 w-36 -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-300/30" />
            <div className="absolute left-1/2 top-1/2 h-52 w-52 -translate-x-1/2 -translate-y-1/2 rounded-full border border-slate-500/30" />
            <div className="absolute left-1/2 top-1/2 h-px w-full -translate-x-1/2 bg-slate-600/50" />
            <div
              className="absolute left-1/2 top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-cyan-300 shadow-[0_0_18px_#22d3ee]"
              title="Earth"
            />
            <div
              className="absolute left-[calc(100%-1rem)] top-1/2 h-5 w-5 -translate-y-1/2 rounded-full bg-amber-300 shadow-[0_0_18px_#fbbf24]"
              title={targetLabel}
            />
            <div
              className="absolute left-1/2 top-1/2 h-0.5 w-[76%] origin-left -translate-y-1/2 rotate-[-18deg] border-t border-dashed border-amber-200/80"
              style={{ transform: `translateZ(${marker3d.z}px) rotate(-18deg)` }}
            />
            <div
              className="absolute left-1/2 top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white bg-amber-300 shadow-[0_0_12px_#fbbf24]"
              style={{
                transform: `translate3d(${marker3d.x}px, ${marker3d.y}px, ${marker3d.z + 12}px)`,
              }}
              title="Spacecraft"
            />
          </div>
          <span className="absolute bottom-2 left-3 text-xs text-muted">Earth</span>
          <span className="absolute bottom-2 right-3 max-w-[45%] truncate text-right text-xs text-muted">
            {targetLabel}
          </span>
          <span className="absolute left-3 top-2 text-xs text-cyan-200">3D transfer view</span>
        </div>
      )}
      <dl className="grid gap-x-4 gap-y-1 text-xs text-muted sm:grid-cols-2">
        <div>
          <dt className="inline font-medium text-foreground">Scenario: </dt>
          <dd className="inline">{mission.scenarioId}</dd>
        </div>
        <div>
          <dt className="inline font-medium text-foreground">Target: </dt>
          <dd className="inline">{targetLabel}</dd>
        </div>
        <div>
          <dt className="inline font-medium text-foreground">Trajectory: </dt>
          <dd className="inline">{trajectoryLabel}</dd>
        </div>
        <div>
          <dt className="inline font-medium text-foreground">Phase: </dt>
          <dd className="inline">
            {phaseLabel(phase)}
            {day === undefined ? "" : ` · day ${day.toFixed(1)}`}
          </dd>
        </div>
      </dl>
      <p className="text-xs text-muted">
        The path is a normalized visual aid for the active mission and selected {providerLabel} trajectory. It does
        not propagate an orbit or change mission calculations.
      </p>
    </section>
  );
}

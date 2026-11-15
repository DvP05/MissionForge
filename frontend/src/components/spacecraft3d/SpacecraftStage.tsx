"use client";

import { Box, Crosshair, Eye, MapPin, RotateCcw, Tag } from "lucide-react";
import { useReducedMotion } from "motion/react";
import { useMotionPref } from "@/components/shell/MotionToggle";
import dynamic from "next/dynamic";
import { useMemo, useState, useSyncExternalStore } from "react";

import {
  busHalfSize,
  GROUP_COLOUR,
  partsForArchitecture,
  VIEW_MODES,
  type CatalogComponent,
  type PartVisual,
} from "@/lib/spacecraft/part-registry";
import { useArchitectUi } from "@/state/architect-ui-store";
import type { MissionState } from "@/state/mission-store";
import type { CameraPreset } from "./SpacecraftViewport";
import { SpacecraftSchematic2D } from "./SpacecraftSchematic2D";

const SpacecraftViewport = dynamic(() => import("./SpacecraftViewport"), {
  ssr: false,
  loading: () => <ViewportMessage text="Loading 3D hangar…" />,
});

function ViewportMessage({ text }: { text: string }) {
  return (
    <div role="status" className="grid h-full place-items-center font-mono text-xs uppercase tracking-[0.2em] text-muted">
      {text}
    </div>
  );
}

// Probed once per page load. getSnapshot runs on every render, and each probe creates a WebGL
// context; browsers cap live contexts (about 16) and then kill the oldest, which would be the
// real viewport. Caching the answer keeps exactly one context alive.
let webglCache: boolean | null = null;
function webglAvailable(): boolean {
  if (webglCache !== null) return webglCache;
  try {
    const c = document.createElement("canvas");
    const gl = (c.getContext("webgl2") ?? c.getContext("webgl")) as WebGLRenderingContext | null;
    webglCache = !!gl;
    gl?.getExtension("WEBGL_lose_context")?.loseContext(); // release the probe context at once
  } catch {
    webglCache = false;
  }
  return webglCache;
}

const subscribeNoop = () => () => {};

const TOOL =
  "inline-flex min-h-8 items-center gap-1 rounded-md border px-2 text-xs font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent-cyan";
const toolClass = (on: boolean) =>
  `${TOOL} ${on ? "border-accent-cyan/60 bg-accent-cyan/15 text-accent-cyan" : "border-border bg-background/70 text-muted hover:text-foreground"}`;

/**
 * Spacecraft viewport with its toolbar (view modes, camera presets, overlays) and an accessible
 * parts list. What is drawn is derived from the canonical MissionState on every render; the
 * 3D scene never decides what is installed.
 */
export function SpacecraftStage({
  mission,
  index,
  height = "h-[26rem] lg:h-[34rem]",
  compact = false,
}: {
  mission: MissionState;
  index: Map<string, CatalogComponent>;
  height?: string;
  compact?: boolean;
}) {
  const ui = useArchitectUi();
  const pref = useMotionPref();
  const reduced = (useReducedMotion() ?? false) || pref === "reduced";
  const [camera, setCamera] = useState<{ preset: CameraPreset; nonce: number }>({ preset: "perspective", nonce: 0 });
  const mounted = useSyncExternalStore(subscribeNoop, () => true, () => false);
  const webgl = useSyncExternalStore(subscribeNoop, webglAvailable, () => true);

  const parts = useMemo(() => partsForArchitecture(mission.architecture, index), [mission.architecture, index]);
  const busHalf = busHalfSize(index, index.get(mission.architecture.busId));
  const modeNote = VIEW_MODES.find((m) => m.mode === ui.mode)?.note ?? "";
  const go = (preset: CameraPreset) => setCamera((c) => ({ preset, nonce: c.nonce + 1 }));
  const select = (p: PartVisual) => ui.select(p.componentId, p.category);

  return (
    <section aria-labelledby="viewport-heading" data-testid="spacecraft-stage" className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-3 py-2">
        <h2 id="viewport-heading" className="flex items-center gap-2 font-mono text-xs uppercase tracking-[0.2em] text-primary">
          <Box aria-hidden className="h-3.5 w-3.5" /> Spacecraft · revision {mission.designRevision}
        </h2>
        <span className="text-[11px] text-muted">Illustrative placeholder geometry · not to scale</span>
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border px-3 py-1.5 text-[11px] text-muted" aria-label="Legend">
        {(Object.entries(GROUP_COLOUR) as [string, string][]).map(([g, c]) => (
          <span key={g} className="inline-flex items-center gap-1">
            <span aria-hidden className="h-2 w-2 rounded-full" style={{ background: c }} />
            {g}
          </span>
        ))}
        <span className="inline-flex items-center gap-1"><span aria-hidden className="h-2 w-3 border border-accent-cyan" />selected</span>
        <span className="inline-flex items-center gap-1"><span aria-hidden className="h-2 w-3 border border-accent-blue" />browsing subsystem</span>
      </div>

      {!compact ? (
        <div role="toolbar" aria-label="View mode" className="flex flex-wrap gap-1 border-b border-border px-3 py-2">
          {VIEW_MODES.map((m) => (
            <button
              key={m.mode}
              type="button"
              data-testid={`view-mode-${m.mode}`}
              aria-pressed={ui.mode === m.mode}
              className={toolClass(ui.mode === m.mode)}
              onClick={() => ui.setMode(m.mode)}
            >
              {m.label}
            </button>
          ))}
        </div>
      ) : null}

      <div className={`hud-grid relative ${height} bg-background-2`}>
        {!mounted ? (
          <ViewportMessage text="Preparing viewport…" />
        ) : webgl ? (
          <SpacecraftViewport
            parts={parts}
            busHalf={busHalf}
            selectedId={ui.selectedId}
            onSelect={(id) => ui.select(id, parts.find((p) => p.componentId === id)?.category)}
            mode={ui.mode}
            labels={ui.labels}
            mounts={ui.mounts}
            wireframe={ui.wireframe || ui.mode === "technical"}
            highlightIds={ui.highlightIds}
            focusNonce={ui.focusNonce}
            camera={camera}
            justInstalled={ui.justInstalled}
            reducedMotion={reduced}
            focusCategory={compact ? null : ui.category}
          />
        ) : (
          <SpacecraftSchematic2D parts={parts} selectedId={ui.selectedId} onSelect={select} />
        )}
        <p data-testid="view-mode-note" className="pointer-events-none absolute bottom-2 left-3 right-3 text-[11px] text-muted">
          {ui.highlightReason ? `Highlighted: ${ui.highlightReason}` : modeNote}
          {mounted && !webgl ? " · WebGL unavailable: 2D schematic shown." : ""}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-1 border-t border-border px-3 py-2" role="toolbar" aria-label="Camera and overlays">
        <button type="button" className={toolClass(false)} onClick={() => go("perspective")} data-testid="camera-reset">
          <RotateCcw aria-hidden className="h-3.5 w-3.5" /> Reset
        </button>
        {(["front", "side", "top"] as const).map((p) => (
          <button key={p} type="button" className={toolClass(false)} onClick={() => go(p)} data-testid={`camera-${p}`}>
            {p[0].toUpperCase() + p.slice(1)}
          </button>
        ))}
        <button type="button" className={toolClass(false)} disabled={!ui.selectedId} onClick={ui.focusSelected} data-testid="camera-focus">
          <Crosshair aria-hidden className="h-3.5 w-3.5" /> Focus selected
        </button>
        <span aria-hidden className="mx-1 h-5 w-px bg-border" />
        <button type="button" aria-pressed={ui.labels} className={toolClass(ui.labels)} onClick={() => ui.toggle("labels")} data-testid="toggle-labels">
          <Tag aria-hidden className="h-3.5 w-3.5" /> Labels
        </button>
        <button type="button" aria-pressed={ui.mounts} className={toolClass(ui.mounts)} onClick={() => ui.toggle("mounts")} data-testid="toggle-mounts">
          <MapPin aria-hidden className="h-3.5 w-3.5" /> Mount points
        </button>
        <button type="button" aria-pressed={ui.wireframe} className={toolClass(ui.wireframe)} onClick={() => ui.toggle("wireframe")} data-testid="toggle-wireframe">
          <Eye aria-hidden className="h-3.5 w-3.5" /> Wireframe
        </button>
      </div>

      <div className="border-t border-border px-3 py-2">
        <p id="parts-list-label" className="mb-1 text-[11px] uppercase tracking-[0.15em] text-muted">
          Installed parts ({parts.length}) · select to inspect
        </p>
        <ul aria-labelledby="parts-list-label" data-testid="part-list" className="flex flex-wrap gap-1">
          {parts.map((p) => (
            <li key={`${p.mountId}:${p.componentId}`}>
              <button
                type="button"
                data-testid={`part-${p.componentId}`}
                aria-pressed={ui.selectedId === p.componentId}
                onClick={() => select(p)}
                className={toolClass(ui.selectedId === p.componentId)}
              >
                <span aria-hidden className="h-2 w-2 rounded-full" style={{ background: GROUP_COLOUR[p.group] }} />
                {p.name}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

"use client";

import { GROUP_COLOUR, type PartVisual } from "@/lib/spacecraft/part-registry";

/**
 * 2D fallback when WebGL is unavailable: a front-view schematic with the same parts, each
 * selectable. Same data as the 3D viewport (the canonical architecture), drawn as boxes.
 */
export function SpacecraftSchematic2D({
  parts,
  selectedId,
  onSelect,
}: {
  parts: PartVisual[];
  selectedId: string | null;
  onSelect: (p: PartVisual) => void;
}) {
  // project mount positions (x, y) onto the SVG; z only orders drawing
  const toSvg = (x: number, y: number) => [160 + x * 70, 130 - y * 70] as const;
  return (
    <svg viewBox="0 0 320 260" className="h-full w-full" data-testid="spacecraft-schematic-2d" role="img" aria-label="Spacecraft schematic (2D fallback)">
      <rect width="320" height="260" fill="#0b0c0c" />
      {parts.map((p) => {
        const [cx, cy] = toSvg(p.position[0], p.position[1]);
        const h = (p.variant.h ?? 0.6) * 70;
        const selected = p.componentId === selectedId;
        const stroke = selected ? "#35d8f2" : GROUP_COLOUR[p.group];
        const common = {
          fill: `${GROUP_COLOUR[p.group]}22`,
          stroke,
          strokeWidth: selected ? 2.5 : 1.2,
          onClick: () => onSelect(p),
          style: { cursor: "pointer" },
        };
        if (p.kind === "bus") return <rect key={p.componentId} x={cx - h} y={cy - h} width={2 * h} height={2 * h} {...common} />;
        if (p.kind === "solar-array") {
          const n = p.variant.panels ?? 2;
          return (
            <g key={p.componentId}>
              <rect x={cx - h - n * 26 - 6} y={cy - h * 0.75} width={n * 26} height={h * 1.5} {...common} />
              <rect x={cx + h + 6} y={cy - h * 0.75} width={n * 26} height={h * 1.5} {...common} />
            </g>
          );
        }
        return <rect key={p.componentId} x={cx - 10} y={cy - 10} width={20} height={20} rx={4} {...common} />;
      })}
    </svg>
  );
}

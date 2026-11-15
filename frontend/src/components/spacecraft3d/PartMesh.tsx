"use client";

import { Edges } from "@react-three/drei";
import { DoubleSide } from "three";
import type { ReactNode } from "react";

import type { PartVisual } from "@/lib/spacecraft/part-registry";

/** Material look of one part in the current view state. */
export interface PartLook {
  colour: string;
  opacity: number;
  wireframe: boolean;
  selected: boolean;
  hovered: boolean;
  /** Part of the subsystem being browsed in the catalogue. */
  focused?: boolean;
  /** Bus wrapped in multi-layer insulation (gold foil) when the thermal choice says so. */
  foil?: boolean;
}

function Mat({ look, colour, metal = 0.6, rough = 0.45, emissive }: { look: PartLook; colour?: string; metal?: number; rough?: number; emissive?: string }) {
  return (
    <meshStandardMaterial
      color={colour ?? look.colour}
      metalness={metal}
      roughness={rough}
      transparent={look.opacity < 1}
      opacity={look.opacity}
      depthWrite={look.opacity >= 1}
      wireframe={look.wireframe}
      emissive={emissive ?? (look.hovered || look.selected ? look.colour : "#000000")}
      emissiveIntensity={emissive ? 0.6 : look.selected ? 0.35 : look.hovered ? 0.2 : 0}
      side={DoubleSide}
    />
  );
}

/** Selection outline on a mesh (cyan, only when the part is selected). */
function Outline({ look }: { look: PartLook }) {
  if (look.selected) return <Edges threshold={20} color="#35d8f2" />;
  return look.focused ? <Edges threshold={20} color="#4d8dff" /> : null;
}

function Box({ size, position, look, colour, metal, rough, emissive, children }: {
  size: [number, number, number];
  position?: [number, number, number];
  look: PartLook;
  colour?: string;
  metal?: number;
  rough?: number;
  emissive?: string;
  children?: ReactNode;
}) {
  return (
    <mesh position={position} castShadow receiveShadow>
      <boxGeometry args={size} />
      <Mat look={look} colour={colour} metal={metal} rough={rough} emissive={emissive} />
      <Outline look={look} />
      {children}
    </mesh>
  );
}

function Cyl({ r1, r2, len, position, rotation, look, colour, open = false, metal, rough, emissive }: {
  r1: number;
  r2: number;
  len: number;
  position?: [number, number, number];
  rotation?: [number, number, number];
  look: PartLook;
  colour?: string;
  open?: boolean;
  metal?: number;
  rough?: number;
  emissive?: string;
}) {
  return (
    <mesh position={position} rotation={rotation} castShadow>
      <cylinderGeometry args={[r1, r2, len, 28, 1, open]} />
      <Mat look={look} colour={colour} metal={metal} rough={rough} emissive={emissive} />
      <Outline look={look} />
    </mesh>
  );
}

/**
 * Procedural placeholder geometry per part kind. Shapes are recognisable stand-ins, not
 * models of real hardware; their sizes follow catalogue rank, never dimensions.
 */
export function PartMesh({ part, look, wingRefs }: { part: PartVisual; look: PartLook; wingRefs?: (el: import("three").Group | null, side: number) => void }) {
  const h = part.variant.h ?? 0.6;
  const X = Math.PI / 2;
  switch (part.kind) {
    case "bus":
      return (
        <group>
          <Box size={[2 * h, 2 * h, 2 * h]} look={look} colour={look.foil ? "#c9982f" : "#5a6a84"} metal={look.foil ? 0.85 : 0.55} rough={look.foil ? 0.32 : 0.5} />
          <Box size={[2 * h + 0.06, 0.04, 2 * h + 0.06]} position={[0, h, 0]} look={look} colour="#8593a8" />
          <Box size={[2 * h + 0.06, 0.04, 2 * h + 0.06]} position={[0, -h, 0]} look={look} colour="#8593a8" />
        </group>
      );
    case "solar-array": {
      const panels = part.variant.panels ?? 2;
      const height = 1.5 * h;
      return (
        <group>
          {[-1, 1].map((side) => (
            <group key={side} position={[side * h, 0, 0]}>
              <group ref={(el) => wingRefs?.(el, side)}>
                <Cyl r1={0.025} r2={0.025} len={0.3} position={[side * 0.15, 0, 0]} rotation={[0, 0, X]} look={look} colour="#9aaac1" />
                {Array.from({ length: panels }, (_, i) => (
                  <Box
                    key={i}
                    size={[0.56, height, 0.03]}
                    position={[side * (0.32 + i * 0.6), 0, 0]}
                    look={look}
                    colour="#2349b0"
                    metal={0.55}
                    rough={0.22}
                    emissive={look.selected ? undefined : "#0c1d55"}
                  />
                ))}
              </group>
            </group>
          ))}
          {/* battery pack on the +X face, lower forward: clear of the wing plane (z = 0) and the -Z radiator */}
          <Box size={[0.14, 0.2, 0.24]} position={[h + 0.07, -0.5 * h, 0.5 * h + 0.06]} look={look} colour="#59482a" />
        </group>
      );
    }
    case "antenna-patch":
      return (
        <group>
          <Cyl r1={0.02} r2={0.02} len={0.3} position={[0.3 * h, 0.15, 0]} look={look} colour="#9aaac1" />
          <Box size={[0.24, 0.03, 0.24]} position={[-0.25 * h, 0.02, 0.25 * h]} look={look} colour="#d8dee9" />
        </group>
      );
    case "antenna-dish": {
      // A spherical-cap reflector. The cap of radius R spans y = -R (vertex) .. -R·cos(0.62)
      // (rim) about its group origin, so the group is lifted by R to sit on the mast.
      const r = part.variant.radius ?? 0.4;
      const R = r * 1.25;
      const rimY = -R * Math.cos(0.62);
      const rim = R * Math.sin(0.62);
      const accent = part.variant.ka ? "#9b7cff" : "#35d8f2";
      return (
        <group>
          <Cyl r1={0.035} r2={0.035} len={0.55} position={[0, 0.275, 0]} look={look} colour="#9aaac1" />
          {/* tilted toward the viewer: illustrative pointing, not a modelled attitude */}
          <group position={[0, 0.55, 0]} rotation={[0.6, 0, 0]}>
            <group position={[0, R, 0]}>
              <mesh rotation={[Math.PI, 0, 0]} castShadow>
                <sphereGeometry args={[R, 36, 14, 0, Math.PI * 2, 0, 0.62]} />
                <Mat look={look} colour="#f2f5fa" metal={0.15} rough={0.4} />
                <Outline look={look} />
              </mesh>
              <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, rimY, 0]}>
                <torusGeometry args={[rim, 0.018, 8, 48]} />
                <Mat look={look} colour={accent} emissive={accent} />
              </mesh>
              <Cyl r1={0.012} r2={0.012} len={0.5 * R + (R + rimY)} position={[0, -R + (0.5 * R + (R + rimY)) / 2, 0]} look={look} colour="#9aaac1" />
              <mesh position={[0, rimY + 0.5 * R, 0]}>
                <sphereGeometry args={[0.05, 16, 12]} />
                <Mat look={look} colour={accent} emissive={accent} />
              </mesh>
            </group>
          </group>
        </group>
      );
    }
    case "nozzle-cluster":
      return (
        <group>
          {[[-1, -1], [1, -1], [-1, 1], [1, 1]].map(([x, z]) => (
            <Cyl key={`${x}${z}`} r1={0.025} r2={0.06} len={0.14} position={[x * 0.75 * h, -0.07, z * 0.75 * h]} look={look} colour="#7d8797" open />
          ))}
          <mesh position={[0, -0.12, 0]}>
            <sphereGeometry args={[0.16, 20, 14]} />
            <Mat look={look} colour="#8a95a8" />
          </mesh>
        </group>
      );
    case "chemical-engine": {
      const tanks = part.variant.tanks ?? 1;
      const big = tanks > 1;
      return (
        <group>
          <Cyl r1={0.06} r2={big ? 0.26 : 0.17} len={big ? 0.5 : 0.36} position={[0, big ? -0.27 : -0.2, 0]} look={look} colour="#6b7280" open metal={0.85} rough={0.3} />
          <Cyl r1={0.09} r2={0.07} len={0.1} position={[0, -0.03, 0]} look={look} colour="#9aaac1" />
          {Array.from({ length: tanks }, (_, i) => (
            <mesh key={i} position={[tanks === 1 ? 0.45 * h : (i === 0 ? -0.55 : 0.55) * h, -0.14, 0.35 * h]}>
              <sphereGeometry args={[0.15, 22, 16]} />
              <Mat look={look} colour="#c7ccd6" metal={0.8} rough={0.25} />
            </mesh>
          ))}
        </group>
      );
    }
    case "ion-engine":
      return (
        <group>
          <Cyl r1={0.3} r2={0.32} len={0.12} position={[0, -0.06, 0]} look={look} colour="#3a475c" />
          <mesh position={[0, -0.125, 0]} rotation={[X, 0, 0]}>
            <circleGeometry args={[0.27, 32]} />
            <meshStandardMaterial color="#4d8dff" emissive="#4d8dff" emissiveIntensity={0.9} transparent={look.opacity < 1} opacity={look.opacity} wireframe={look.wireframe} />
          </mesh>
          <mesh position={[0.45 * h, -0.14, 0.35 * h]}>
            <sphereGeometry args={[0.13, 20, 14]} />
            <Mat look={look} colour="#c7ccd6" metal={0.8} rough={0.25} />
          </mesh>
        </group>
      );
    case "reaction-wheels":
      return (
        <group position={[0, 0.08, 0]}>
          <Cyl r1={0.08} r2={0.08} len={0.05} look={look} colour="#4d8dff" />
          <Cyl r1={0.08} r2={0.08} len={0.05} position={[0.18, 0.08, 0]} rotation={[0, 0, X]} look={look} colour="#4d8dff" />
          <Cyl r1={0.08} r2={0.08} len={0.05} position={[0, 0.08, 0.18]} rotation={[X, 0, 0]} look={look} colour="#4d8dff" />
        </group>
      );
    case "star-tracker":
      return (
        <group>
          {Array.from({ length: part.variant.heads ?? 1 }, (_, i) => (
            <group key={i} position={[i * 0.22, 0.12, 0]} rotation={[0.35, 0, -0.35]}>
              <Cyl r1={0.075} r2={0.045} len={0.22} look={look} colour="#20293a" open />
              <Box size={[0.12, 0.08, 0.12]} position={[0, -0.13, 0]} look={look} colour="#4d8dff" />
            </group>
          ))}
        </group>
      );
    case "insulation":
      return (
        <mesh>
          <boxGeometry args={[2 * h + 0.05, 2 * h + 0.05, 2 * h + 0.05]} />
          <meshStandardMaterial color="#d6a640" metalness={0.9} roughness={0.35} transparent opacity={Math.min(look.opacity, 0.22)} depthWrite={false} wireframe={look.wireframe} />
          <Outline look={look} />
        </mesh>
      );
    case "heater-strips":
      return (
        <group>
          {[-0.5, 0, 0.5].map((y) => (
            <Box key={y} size={[1.4 * h, 0.05, 0.02]} position={[0, y * h, -0.012]} look={look} colour="#ff9f43" emissive="#ff7a1a" />
          ))}
        </group>
      );
    case "radiator":
      return (
        <group>
          <Box size={[1.7 * h, 1.7 * h, 0.03]} position={[0, 0, -0.02]} look={look} colour="#e8edf4" metal={0.2} rough={0.2} />
          {[-0.6, -0.2, 0.2, 0.6].map((x) => (
            <Box key={x} size={[0.02, 1.6 * h, 0.04]} position={[x * h, 0, -0.05]} look={look} colour="#b9c2cf" />
          ))}
          <Box size={[1.2 * h, 0.05, 0.02]} position={[0, -0.95 * h, -0.02]} look={look} colour="#ff9f43" emissive="#ff7a1a" />
        </group>
      );
    case "avionics-box":
      return (
        <group>
          <Box size={[0.14, 0.32, 0.4]} position={[-0.07, 0, 0]} look={look} colour="#26324a" />
          {[-0.1, 0, 0.1].map((y) => (
            <Box key={y} size={[0.01, 0.03, 0.3]} position={[-0.145, y, 0]} look={look} colour="#4d8dff" emissive="#1f4fbf" />
          ))}
        </group>
      );
    case "camera": {
      const r = part.variant.large ? 0.12 : 0.08;
      const len = part.variant.large ? 0.42 : 0.26;
      return (
        <group>
          <Cyl r1={r} r2={r} len={len} position={[0, 0, len / 2]} rotation={[X, 0, 0]} look={look} colour="#1d2533" />
          <Cyl r1={r * 1.15} r2={r * 1.15} len={0.04} position={[0, 0, len]} rotation={[X, 0, 0]} look={look} colour="#9b7cff" open />
          <mesh position={[0, 0, len + 0.002]}>
            <circleGeometry args={[r * 0.85, 28]} />
            <meshStandardMaterial color="#0a0f1a" metalness={1} roughness={0.05} transparent={look.opacity < 1} opacity={look.opacity} />
          </mesh>
        </group>
      );
    }
    case "spectrometer":
      return (
        <group>
          <Box size={[0.3, 0.2, 0.22]} position={[0, 0, 0.11]} look={look} colour="#2b2450" />
          <Cyl r1={0.05} r2={0.05} len={0.1} position={[0.06, 0.02, 0.27]} rotation={[X, 0, 0]} look={look} colour="#9b7cff" />
        </group>
      );
    case "radiometer":
      return (
        <group>
          <Box size={[0.24, 0.22, 0.2]} position={[0, 0, 0.1]} look={look} colour="#2b2450" />
          {[-0.08, 0, 0.08].map((x) => (
            <Box key={x} size={[0.015, 0.2, 0.08]} position={[x, 0, 0.24]} look={look} colour="#c9b8ff" />
          ))}
        </group>
      );
    case "boom":
      // a straight deployable mast along local +Y (the mount rotates it outward and down)
      return (
        <group>
          <Cyl r1={0.05} r2={0.05} len={0.06} position={[0, 0.03, 0]} look={look} colour="#7d8797" />
          <Cyl r1={0.015} r2={0.015} len={1.1} position={[0, 0.6, 0]} look={look} colour="#c9d2df" />
          <mesh position={[0, 1.18, 0]}>
            <sphereGeometry args={[0.06, 18, 12]} />
            <Mat look={look} colour="#9b7cff" />
          </mesh>
        </group>
      );
    case "launch-adapter":
      return (
        <group>
          <mesh rotation={[X, 0, 0]}>
            <torusGeometry args={[0.5 * h + 0.15, 0.035, 12, 48]} />
            <Mat look={look} colour="#7d8797" />
          </mesh>
          <Cyl r1={0.5 * h + 0.15} r2={0.42 * h + 0.1} len={0.18} position={[0, -0.1, 0]} look={look} colour="#525c6c" open />
        </group>
      );
  }
}

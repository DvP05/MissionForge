"use client";

import { Environment, Html, Lightformer, OrbitControls, Stars } from "@react-three/drei";
import { Canvas, useThree, type ThreeEvent } from "@react-three/fiber";
import { animate } from "animejs";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Group } from "three";
import { Box3, Vector3, type Object3D } from "three";

import {
  mountPoints,
  partEmphasis,
  type PartVisual,
  type SubsystemGroup,
  type Vec3,
  type ViewMode,
} from "@/lib/spacecraft/part-registry";
import { PartMesh } from "./PartMesh";

export type CameraPreset = "perspective" | "front" | "side" | "top";

export interface ViewportProps {
  parts: PartVisual[];
  busHalf: number;
  selectedId: string | null;
  onSelect: (componentId: string) => void;
  mode: ViewMode;
  labels: boolean;
  mounts: boolean;
  wireframe: boolean;
  highlightIds: string[];
  focusNonce: number;
  camera: { preset: CameraPreset; nonce: number };
  justInstalled: { componentId: string; nonce: number } | null;
  reducedMotion: boolean;
  /** Subsystem being browsed: its parts get an outline, its empty slots are shown. */
  focusCategory?: string | null;
}

const PRESETS: Record<CameraPreset, Vec3> = {
  perspective: [4.2, 2.8, 5.2],
  front: [0, 0.3, 6.2],
  side: [6.2, 0.3, 0],
  top: [0, 6.4, 0.01],
};

const add = (a: Vec3, b: Vec3, k = 1): Vec3 => [a[0] + b[0] * k, a[1] + b[1] * k, a[2] + b[2] * k];

/** One installed part: its placement, exploded offset, emphasis and install animation. */
function Part({
  part,
  props,
  foil,
  installNonce,
}: {
  part: PartVisual;
  props: ViewportProps;
  foil: boolean;
  installNonce: number | null;
}) {
  const ref = useRef<Group>(null);
  const wings = useRef<Map<number, Group>>(new Map());
  const invalidate = useThree((s) => s.invalidate);
  const [hovered, setHovered] = useState(false);
  const selectedGroup: SubsystemGroup | null = props.parts.find((p) => p.componentId === props.selectedId)?.group ?? null;
  const emphasis = partEmphasis(part, props.mode, selectedGroup, new Set(props.highlightIds));
  const exploded = props.mode === "exploded";
  const target = add(part.position, part.normal, exploded ? part.explodeDistance : 0);

  // Exploded <-> assembled: anime.js moves the group to its target (instant if reduced motion).
  useEffect(() => {
    const g = ref.current;
    if (!g) return;
    if (props.reducedMotion) {
      g.position.set(...target);
      invalidate();
      return;
    }
    const anim = animate(g.position, {
      x: target[0],
      y: target[1],
      z: target[2],
      duration: 650,
      ease: "outCubic",
      onUpdate: () => invalidate(),
    });
    return () => {
      anim.pause();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- target is derived from these
  }, [exploded, part.position[0], part.position[1], part.position[2], props.reducedMotion]);

  // Install sequence: fly in along the mount normal, settle with a small overshoot, then
  // deploy solar wings. Runs only for the part the player just installed.
  useEffect(() => {
    const g = ref.current;
    if (!g || installNonce === null || props.reducedMotion) return;
    const start = add(target, part.normal[0] || part.normal[1] || part.normal[2] ? part.normal : [0, 1, 0], 2.4);
    g.position.set(...start);
    g.scale.setScalar(0.4);
    const fly = animate(g.position, { x: target[0], y: target[1], z: target[2], duration: 700, ease: "outBack(1.3)", onUpdate: () => invalidate() });
    const grow = animate(g.scale, { x: 1, y: 1, z: 1, duration: 600, ease: "outBack(1.6)", onUpdate: () => invalidate() });
    const deploys = [...wings.current.values()].map((w) => {
      w.scale.x = 0.05;
      return animate(w.scale, { x: 1, delay: 550, duration: 900, ease: "outElastic(1, .7)", onUpdate: () => invalidate() });
    });
    return () => {
      fly.pause();
      grow.pause();
      deploys.forEach((d) => d.pause());
      g.scale.setScalar(1);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- replay only on a new install
  }, [installNonce]);

  if (emphasis === "hidden") return null;
  const look = {
    colour: part.colour,
    opacity: emphasis === "dim" ? 0.16 : 1,
    wireframe: props.wireframe,
    selected: props.selectedId === part.componentId,
    focused: props.focusCategory === part.category,
    hovered,
    foil,
  };
  const labelAt = add([0, 0, 0], part.normal[0] || part.normal[1] || part.normal[2] ? part.normal : [0, 1, 0], 0.55);

  return (
    <group
      ref={ref}
      userData={{ componentId: part.componentId, category: part.category, kind: part.kind }}
      position={target}
      onClick={(e: ThreeEvent<MouseEvent>) => {
        e.stopPropagation();
        props.onSelect(part.componentId);
      }}
      onPointerOver={(e) => {
        e.stopPropagation();
        setHovered(true);
        document.body.style.cursor = "pointer";
        invalidate();
      }}
      onPointerOut={() => {
        setHovered(false);
        document.body.style.cursor = "";
        invalidate();
      }}
    >
      <group rotation={part.rotation}>
        <PartMesh
          part={part}
          look={look}
          wingRefs={(el, side) => {
            if (el) wings.current.set(side, el);
            else wings.current.delete(side);
          }}
        />
      </group>
      {props.labels && emphasis !== "dim" ? (
        <Html position={labelAt} center distanceFactor={4.5} zIndexRange={[20, 0]}>
          <span className="pointer-events-none whitespace-nowrap rounded border border-accent-cyan/40 bg-background/85 px-1 py-px font-mono text-[9px] text-foreground">
            {part.name}
          </span>
        </Html>
      ) : null}
    </group>
  );
}

/** Mount-point markers (technical overlay): filled when a part occupies the mount. */
function Mounts({ busHalf, occupied, pulseMount }: { busHalf: number; occupied: Set<string>; pulseMount: string | null }) {
  const points = useMemo(() => mountPoints(busHalf), [busHalf]);
  return (
    <group>
      {points
        .filter((m) => m.mountId !== "mount-bus")
        .map((m) => {
          const on = occupied.has(m.mountId);
          const pulse = pulseMount === m.mountId;
          return (
            <mesh key={m.mountId} position={add(m.position, m.normal, 0.02)}>
              <sphereGeometry args={[pulse ? 0.09 : 0.05, 14, 10]} />
              <meshBasicMaterial color={pulse ? "#45d69a" : on ? "#35d8f2" : "#65758d"} transparent opacity={on || pulse ? 0.95 : 0.6} />
            </mesh>
          );
        })}
    </group>
  );
}

/** Empty payload slots, shown while instruments are being browsed (the free mounts). */
function EmptySlots({ busHalf, occupied, labels }: { busHalf: number; occupied: Set<string>; labels: boolean }) {
  const free = useMemo(
    () => mountPoints(busHalf).filter((m) => m.mountId.startsWith("mount-instrument-") && !occupied.has(m.mountId)),
    [busHalf, occupied],
  );
  return (
    <group>
      {free.map((m) => (
        <mesh key={m.mountId} position={add(m.position, m.normal, 0.08)}>
          <boxGeometry args={[0.22, 0.18, 0.16]} />
          <meshBasicMaterial color="#35d8f2" wireframe transparent opacity={0.45} />
          {labels ? (
            <Html center distanceFactor={4.5} zIndexRange={[20, 0]}>
              <span className="pointer-events-none whitespace-nowrap rounded border border-dashed border-accent-cyan/50 bg-background/80 px-1 font-mono text-[9px] text-muted">
                empty slot
              </span>
            </Html>
          ) : null}
        </mesh>
      ))}
    </group>
  );
}

/**
 * Development-only geometry probe: lists pairs of installed parts whose bounding boxes
 * intersect, so placement can be checked automatically (e2e) instead of by eye. Mesh boxes are
 * computed per mesh (not per group) so a thin boom does not count as a solid block.
 */
function SceneProbe() {
  const scene = useThree((s) => s.scene);
  useEffect(() => {
    if (process.env.NODE_ENV === "production") return;
    const w = window as unknown as { __spacecraftOverlaps?: (minVolume?: number) => string[] };
    w.__spacecraftOverlaps = (minVolume = 1e-4) => {
      const parts: { id: string; kind: string; boxes: Box3[] }[] = [];
      scene.updateMatrixWorld(true);
      scene.traverse((o: Object3D) => {
        const id = o.userData?.componentId as string | undefined;
        if (!id) return;
        const boxes: Box3[] = [];
        o.traverse((m) => {
          const mesh = m as Object3D & { isMesh?: boolean };
          if (mesh.isMesh && mesh.visible) boxes.push(new Box3().setFromObject(mesh));
        });
        parts.push({ id, kind: o.userData.kind as string, boxes });
      });
      const out: string[] = [];
      const vol = (b: Box3) => {
        const s = new Vector3();
        b.getSize(s);
        return Math.max(0, s.x) * Math.max(0, s.y) * Math.max(0, s.z);
      };
      for (let i = 0; i < parts.length; i += 1) {
        for (let j = i + 1; j < parts.length; j += 1) {
          const a = parts[i];
          const b = parts[j];
          // the bus carries everything and the MLI shell wraps it: contact with them is by design
          if ([a.kind, b.kind].some((k) => k === "bus" || k === "insulation")) continue;
          let worst = 0;
          for (const x of a.boxes) for (const y of b.boxes) if (x.intersectsBox(y)) worst = Math.max(worst, vol(x.clone().intersect(y)));
          if (worst > minVolume) out.push(`${a.id} x ${b.id} (${worst.toExponential(1)} m3)`);
        }
      }
      return out;
    };
  }, [scene]);
  return null;
}

/** Camera presets and focus, animated with anime.js on the camera and the orbit target. */
function CameraRig({ props }: { props: ViewportProps }) {
  const camera = useThree((s) => s.camera);
  const controls = useThree((s) => s.controls);
  const invalidate = useThree((s) => s.invalidate);

  const fly = (to: Vec3, lookAt: Vec3) => {
    const orbit = controls as unknown as { target: Vector3; update: () => void } | null;
    if (props.reducedMotion) {
      camera.position.set(...to);
      orbit?.target.set(...lookAt);
      orbit?.update();
      invalidate();
      return;
    }
    animate(camera.position, { x: to[0], y: to[1], z: to[2], duration: 700, ease: "inOutCubic", onUpdate: () => { orbit?.update(); invalidate(); } });
    if (orbit) animate(orbit.target, { x: lookAt[0], y: lookAt[1], z: lookAt[2], duration: 700, ease: "inOutCubic" });
  };

  useEffect(() => {
    if (props.camera.nonce === 0) return;
    fly(PRESETS[props.camera.preset], [0, 0, 0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run per request
  }, [props.camera.nonce]);

  useEffect(() => {
    if (props.focusNonce === 0) return;
    const p = props.parts.find((x) => x.componentId === props.selectedId);
    if (!p) return;
    const at = add(p.position, p.normal, props.mode === "exploded" ? p.explodeDistance : 0);
    const dir = new Vector3(...add(p.normal, [0.5, 0.45, 0.6])).normalize().multiplyScalar(3.2);
    fly([at[0] + dir.x, at[1] + dir.y, at[2] + dir.z], at);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run per request
  }, [props.focusNonce]);

  return null;
}

/**
 * The interactive 3D spacecraft (React Three Fiber). Rendering is on demand: frames are drawn
 * only when the camera, a part or an animation changes. Loaded lazily; never server-rendered.
 */
export default function SpacecraftViewport(props: ViewportProps) {
  const occupied = useMemo(() => new Set(props.parts.map((p) => p.mountId)), [props.parts]);
  const foil = props.parts.some((p) => p.kind === "insulation");
  const installedMount =
    props.justInstalled && props.parts.find((p) => p.componentId === props.justInstalled?.componentId)?.mountId;

  return (
    <Canvas
      frameloop="demand"
      dpr={[1, 2]}
      shadows="percentage"
      camera={{ position: PRESETS.perspective, fov: 40, near: 0.1, far: 200 }}
      onPointerMissed={() => undefined}
      gl={{ antialias: true, preserveDrawingBuffer: true }}
      data-testid="spacecraft-canvas"
    >
      <color attach="background" args={["#0b0c0c"]} />
      <hemisphereLight args={["#9fc4ff", "#120a24", 0.55]} />
      <directionalLight position={[6, 8, 5]} intensity={2.1} color="#fff1dc" castShadow />
      <directionalLight position={[-6, -2, -5]} intensity={0.9} color="#9b7cff" />
      <pointLight position={[0, -4, 3]} intensity={6} color="#35d8f2" distance={10} />
      <Stars radius={60} depth={30} count={1800} factor={3} saturation={0} fade speed={0} />
      {/* Local reflection environment (light panels baked once; nothing is downloaded). */}
      <Environment resolution={128} frames={1}>
        <Lightformer form="rect" intensity={2.4} color="#fff3e0" position={[5, 6, 4]} scale={[8, 4, 1]} />
        <Lightformer form="rect" intensity={1.2} color="#9fc4ff" position={[-6, 2, -3]} scale={[6, 6, 1]} />
        <Lightformer form="ring" intensity={1.5} color="#35d8f2" position={[0, -6, 4]} scale={4} />
        <Lightformer form="rect" intensity={0.8} color="#9b7cff" position={[0, 4, -7]} scale={[10, 3, 1]} />
      </Environment>
      <group>
        {props.parts.map((part) => (
          <Part
            key={`${part.mountId}:${part.componentId}`}
            part={part}
            props={props}
            foil={foil && part.kind === "bus"}
            installNonce={props.justInstalled?.componentId === part.componentId ? props.justInstalled.nonce : null}
          />
        ))}
        {props.mounts ? <Mounts busHalf={props.busHalf} occupied={occupied} pulseMount={installedMount ?? null} /> : null}
        {props.focusCategory === "instrument" ? <EmptySlots busHalf={props.busHalf} occupied={occupied} labels={props.labels} /> : null}
      </group>
      <gridHelper args={[14, 28, "#4a4f50", "#262a2b"]} position={[0, -props.busHalf - 1.3, 0]} />
      <OrbitControls makeDefault enableDamping={false} minDistance={2} maxDistance={16} />
      <CameraRig props={props} />
      <SceneProbe />
    </Canvas>
  );
}

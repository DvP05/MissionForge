"use client";

import { Play, Swords } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { FidelityBadge } from "@/components/common/FidelityBadge";
import { StatusPill } from "@/components/common/StatusPill";
import { ACTION_CLASS } from "@/components/common/States";
import { apiPost } from "@/lib/api-client";
import type { components } from "@/lib/api/schema";
import { formatFraction, formatNumber } from "@/lib/format";
import { useMissionStore, type ComponentCategory } from "@/state/mission-store";

type OptimizeData = components["schemas"]["OptimizeData"];
type Candidate = components["schemas"]["CandidateSummary"];
type Architecture = components["schemas"]["SpacecraftArchitecture"];

/**
 * Categorical slots 1-3 of the validated dataviz palette, dark steps, checked all-pairs
 * against this app's #111827 surface (CVD dE 9.4, normal-vision dE 20.9, >= 3:1).
 * Each group also has its own marker shape, so colour is never the only cue.
 */
const GROUPS = {
  front: { label: "Pareto front", color: "#3987e5", shape: "circle" },
  feasible: { label: "Other feasible designs", color: "#199e70", shape: "diamond" },
  near: { label: "Near misses (break a hard limit)", color: "#d95926", shape: "cross" },
} as const;
type GroupKey = keyof typeof GROUPS;

const ARCHETYPE_LABEL: Record<string, string> = {
  lean: "Lean",
  "science-max": "Science-max",
  resilient: "Resilient",
};

/** Architecture field per single-select catalogue category (mirrors the store). */
const FIELD: Record<Exclude<ComponentCategory, "instrument">, keyof Architecture> = {
  launch: "launchVehicleId",
  bus: "busId",
  propulsion: "propulsionId",
  power: "powerId",
  adcs: "adcsId",
  communications: "communicationsId",
  thermal: "thermalId",
  cdh: "cdhId",
  ground: "groundSegmentId",
};

interface Point {
  id: string;
  x: number; // estimated cost, million USD (display scaling only)
  y: number; // science coverage score
  group: GroupKey;
}

type Run =
  | { kind: "idle" }
  | { kind: "running" }
  | { kind: "done"; data: OptimizeData }
  | { kind: "error"; message: string };

function PointTooltip({ active, payload }: { active?: boolean; payload?: { payload?: Point }[] }) {
  const p = active ? payload?.[0]?.payload : undefined;
  if (!p) return null;
  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-2 text-xs shadow-lg">
      <p className="font-medium">{GROUPS[p.group].label}</p>
      <p>Cost: {formatNumber(p.x)} M USD</p>
      <p>Science coverage: {formatNumber(p.y)}</p>
      <p className="text-muted">Click to inspect</p>
    </div>
  );
}

/**
 * Mission Design Arena (Task 6.2): generates up to 250 candidate designs from the current
 * one, shows cost vs science, highlights the feasible Pareto front and three named
 * representatives, and loads any candidate into the Architect. All numbers come from the
 * backend engine; the chart only plots them.
 */
export function ParetoExplorer() {
  const router = useRouter();
  const mission = useMissionStore((s) => s.mission);
  const [run, setRun] = useState<Run>({ kind: "idle" });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showNear, setShowNear] = useState(true);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);

  const data = run.kind === "done" ? run.data : null;
  const byId = useMemo(() => new Map(data?.candidates.map((c) => [c.id, c]) ?? []), [data]);
  const archetypeOf = useMemo(() => {
    const out = new Map<string, string[]>();
    for (const [name, id] of Object.entries(data?.archetypes ?? {})) {
      if (id) out.set(id, [...(out.get(id) ?? []), ARCHETYPE_LABEL[name] ?? name]);
    }
    return out;
  }, [data]);
  const points = useMemo(() => {
    const front = new Set(data?.paretoFrontIds ?? []);
    const groups: Record<GroupKey, Point[]> = { front: [], feasible: [], near: [] };
    for (const c of data?.candidates ?? []) {
      const group: GroupKey = !c.feasible ? "near" : front.has(c.id) ? "front" : "feasible";
      groups[group].push({ id: c.id, x: c.estimatedCostUsd / 1e6, y: c.scienceCoverageScore, group });
    }
    return groups;
  }, [data]);

  if (!mission) return null;

  const execute = async () => {
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    setRun({ kind: "running" });
    setSelectedId(null);
    const response = await apiPost(
      "/api/mission/optimize",
      { missionState: mission, cap: 150, robustnessSamples: 20 },
      { signal: abort.signal, timeoutMs: 30_000 },
    );
    if (abort.signal.aborted) return;
    if (response.ok && response.data) {
      setRun({ kind: "done", data: response.data });
      setSelectedId(response.data.archetypes.lean ?? response.data.paretoFrontIds[0] ?? null);
    } else {
      setRun({ kind: "error", message: response.error?.message ?? "The design arena could not run." });
    }
  };

  const outdated = data !== null && data.designRevision !== mission.designRevision;
  const selected = selectedId ? byId.get(selectedId) ?? null : null;
  const baseline = data?.candidates.find((c) => c.generation === 0) ?? null;

  const loadIntoArchitect = (c: Candidate) => {
    const store = useMissionStore.getState();
    const current = store.mission;
    if (!current) return;
    for (const [category, field] of Object.entries(FIELD) as [ComponentCategory, keyof Architecture][]) {
      const next = c.architecture[field];
      if (typeof next === "string" && current.architecture[field] !== next) store.selectComponent(category, next);
    }
    const want = new Set(c.architecture.instrumentIds);
    const have = new Set(useMissionStore.getState().mission?.architecture.instrumentIds ?? []);
    for (const id of have) if (!want.has(id)) store.selectComponent("instrument", id);
    for (const id of want) if (!have.has(id)) store.selectComponent("instrument", id);
    store.commitRevision();
    router.push(`/architect/${current.missionId}`);
  };

  return (
    <section
      aria-labelledby="arena-title"
      data-testid="pareto-explorer"
      className="space-y-4 rounded-xl border border-border bg-surface/40 p-4"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h2 id="arena-title" className="flex items-center gap-2 text-lg font-semibold">
            <Swords aria-hidden className="h-5 w-5 text-accent-cyan" />
            Mission Design Arena
          </h2>
          <p className="max-w-3xl text-sm text-muted">
            The engine builds up to 150 variations of your current design (swapping one or two parts, plus random
            combinations) and checks each one. The Pareto front holds the designs you cannot beat on cost, mass and
            science at the same time. There is no single &quot;best&quot; design, only trade-offs.
          </p>
        </div>
        <FidelityBadge fidelity="derived" />
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          data-testid="arena-run"
          onClick={execute}
          disabled={run.kind === "running"}
          className={`${ACTION_CLASS} gap-2 disabled:opacity-50`}
        >
          <Play aria-hidden className="h-4 w-4" />
          {run.kind === "running" ? "Exploring designs..." : `Explore from revision ${mission.designRevision}`}
        </button>
        {outdated ? (
          <StatusPill tone="warn">Results are for revision {data?.designRevision}; explore again for the current design</StatusPill>
        ) : null}
        {data ? (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={showNear} onChange={(e) => setShowNear(e.target.checked)} />
            Show near misses ({data.nearMisses.length})
          </label>
        ) : null}
      </div>

      {run.kind === "error" ? (
        <p role="alert" className="text-sm text-red-300">
          {run.message}
        </p>
      ) : null}

      {data ? (
        <div className="space-y-4" data-testid="arena-result">
          <p className="text-sm text-muted">
            {data.candidates.length} designs checked: {data.candidates.length - data.nearMisses.length} feasible,{" "}
            {data.paretoFrontIds.length} on the Pareto front, {data.nearMisses.length} near misses. Seed {data.seed}.
          </p>

          <div className="flex flex-wrap gap-2" data-testid="arena-archetypes">
            {(["lean", "science-max", "resilient"] as const).map((name) => {
              const id = data.archetypes[name];
              return id ? (
                <button
                  key={name}
                  type="button"
                  data-testid={`archetype-${name}`}
                  aria-pressed={selectedId === id}
                  onClick={() => setSelectedId(id)}
                  className={`min-h-11 rounded-lg border px-4 text-sm font-medium ${
                    selectedId === id ? "border-accent-cyan bg-accent-cyan/10 text-accent-cyan" : "border-border"
                  }`}
                >
                  {ARCHETYPE_LABEL[name]}
                </button>
              ) : null;
            })}
            {Object.keys(data.archetypes).length === 0 ? (
              <p className="text-sm text-accent-amber">
                No feasible design was found nearby. Open a near miss to see which limit it breaks.
              </p>
            ) : null}
          </div>

          <div className="grid gap-4 xl:grid-cols-[1fr_24rem]">
            <figure className="min-w-0 space-y-2">
              <figcaption className="text-sm font-medium">Estimated cost vs science coverage score</figcaption>
              <div className="h-80 w-full" data-testid="arena-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ top: 8, right: 16, bottom: 28, left: 8 }}>
                    <CartesianGrid stroke="#243044" strokeDasharray="3 3" />
                    <XAxis
                      type="number"
                      dataKey="x"
                      name="Cost"
                      unit=" M"
                      domain={["auto", "auto"]}
                      tick={{ fill: "#8fa0b8", fontSize: 12 }}
                      stroke="#243044"
                      label={{ value: "Estimated cost (million USD)", position: "bottom", fill: "#8fa0b8", fontSize: 12 }}
                    />
                    <YAxis
                      type="number"
                      dataKey="y"
                      name="Science"
                      domain={[0, 100]}
                      tick={{ fill: "#8fa0b8", fontSize: 12 }}
                      stroke="#243044"
                      width={40}
                    />
                    <Tooltip content={<PointTooltip />} cursor={{ stroke: "#8fa0b8", strokeDasharray: "3 3" }} />
                    <Legend verticalAlign="top" height={28} wrapperStyle={{ fontSize: 12, color: "#e6edf7" }} />
                    {(Object.keys(GROUPS) as GroupKey[])
                      .filter((g) => g !== "near" || showNear)
                      .map((g) => (
                        <Scatter
                          key={g}
                          name={GROUPS[g].label}
                          data={points[g]}
                          fill={GROUPS[g].color}
                          stroke="#111827"
                          strokeWidth={2}
                          shape={GROUPS[g].shape}
                          isAnimationActive={false}
                          cursor="pointer"
                          onClick={(p: unknown) => {
                            const id = (p as { payload?: Point; id?: string })?.payload?.id ?? (p as { id?: string })?.id;
                            if (id) setSelectedId(id);
                          }}
                        />
                      ))}
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
              <p className="text-xs text-muted">
                Higher and further left is better. Mass is the third objective and is shown in the details.
              </p>
            </figure>

            {selected ? (
              <div data-testid="arena-detail" className="space-y-3 rounded-xl border border-border bg-surface p-4 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  {(archetypeOf.get(selected.id) ?? []).map((a) => (
                    <StatusPill key={a} tone="info">
                      {a}
                    </StatusPill>
                  ))}
                  <StatusPill tone={selected.feasible ? "ok" : "danger"}>
                    {selected.feasible ? "Feasible" : "Near miss"}
                  </StatusPill>
                  {selected.generation === 0 ? <StatusPill>Your current design</StatusPill> : null}
                </div>
                <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
                  <dt className="text-muted">Estimated cost</dt>
                  <dd>{formatNumber(selected.estimatedCostUsd / 1e6)} M USD</dd>
                  <dt className="text-muted">Dry mass</dt>
                  <dd>{formatNumber(selected.dryMassKg)} kg</dd>
                  <dt className="text-muted">Science coverage</dt>
                  <dd>{formatNumber(selected.scienceCoverageScore)}</dd>
                  <dt className="text-muted">Science returned</dt>
                  <dd>{formatFraction(selected.returnedFraction)}</dd>
                  <dt className="text-muted">Mission score</dt>
                  <dd>{formatNumber(selected.scoreTotal)}</dd>
                </dl>
                {baseline && selected.id !== baseline.id ? (
                  <p className="text-xs text-muted">
                    Compared with your design: cost{" "}
                    {formatNumber((selected.estimatedCostUsd - baseline.estimatedCostUsd) / 1e6)} M USD, science{" "}
                    {formatNumber(selected.scienceCoverageScore - baseline.scienceCoverageScore)} points.
                  </p>
                ) : null}
                <ul className="list-disc space-y-1 pl-5" data-testid="arena-explanation">
                  {selected.explanation.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
                {selected.generation !== 0 ? (
                  <button
                    type="button"
                    data-testid="arena-load"
                    onClick={() => loadIntoArchitect(selected)}
                    className={ACTION_CLASS}
                  >
                    Load this design into the Architect
                  </button>
                ) : null}
              </div>
            ) : (
              <p className="rounded-xl border border-dashed border-border p-4 text-sm text-muted">
                Click a point or a named design to inspect it.
              </p>
            )}
          </div>

          <details className="rounded-xl border border-border bg-surface p-4 text-sm">
            <summary className="cursor-pointer font-medium">Pareto front as a table ({data.paretoFrontIds.length})</summary>
            <table className="mt-2 w-full text-left text-sm" data-testid="arena-front-table">
              <thead className="text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="py-1 pr-3 font-medium">Design</th>
                  <th scope="col" className="py-1 pr-3 font-medium">Cost (M USD)</th>
                  <th scope="col" className="py-1 pr-3 font-medium">Dry mass (kg)</th>
                  <th scope="col" className="py-1 pr-3 font-medium">Science</th>
                </tr>
              </thead>
              <tbody>
                {data.paretoFrontIds.map((id) => {
                  const c = byId.get(id);
                  if (!c) return null;
                  return (
                    <tr key={id} className="border-t border-border">
                      <td className="py-1 pr-3">
                        <button type="button" className="text-accent-cyan hover:underline" onClick={() => setSelectedId(id)}>
                          {(archetypeOf.get(id) ?? []).join(", ") || id}
                        </button>
                      </td>
                      <td className="py-1 pr-3 font-mono text-xs">{formatNumber(c.estimatedCostUsd / 1e6)}</td>
                      <td className="py-1 pr-3 font-mono text-xs">{formatNumber(c.dryMassKg)}</td>
                      <td className="py-1 pr-3 font-mono text-xs">{formatNumber(c.scienceCoverageScore)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </details>
        </div>
      ) : null}
    </section>
  );
}

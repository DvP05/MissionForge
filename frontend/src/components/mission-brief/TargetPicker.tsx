"use client";

import { Database, Satellite } from "lucide-react";
import { useEffect, useState } from "react";

import { FidelityBadge } from "@/components/common/FidelityBadge";
import { StatusPill } from "@/components/common/StatusPill";
import { ACTION_CLASS } from "@/components/common/States";
import { apiGet } from "@/lib/api-client";
import type { components } from "@/lib/api/schema";
import { formatNumber } from "@/lib/format";
import { useMissionStore } from "@/state/mission-store";

type Data = components["schemas"]["NeoAccessibleData"];
type Option = components["schemas"]["JplMissionOption"];
type Source = components["schemas"]["SourceInfo"];
type Load = { status: "loading" } | { status: "error" } | { status: "ready"; data: Data };

/** Human source label: never says LIVE unless the backend fetched it just now. */
export function sourceLabel(src: Source): string {
  const day = src.retrievedAt ? src.retrievedAt.slice(0, 10) : null;
  if (src.status === "live") return "LIVE — JPL API";
  if (src.status === "cached") return `CACHED — retrieved ${day ?? "earlier"}`;
  if (src.synthetic) return "SYNTHETIC — not JPL data";
  return `DEMO — captured ${day ?? "offline"}`;
}

/**
 * Phase 5 (AC-08/09, architecture 12.7): NEO targets from the JPL Mission Design API, always
 * through the MISSIONFORGE backend (never fetched from the browser). Choosing one writes a
 * ``jpl-mdesign`` trajectory with the server's source reference; the engine keeps C3 as
 * launch energy and never adds it to spacecraft delta-v.
 */
export function TargetPicker() {
  const mission = useMissionStore((s) => s.mission);
  const setTrajectory = useMissionStore((s) => s.setTrajectory);
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const isNeo = mission?.scenarioId === "neo-rendezvous";

  useEffect(() => {
    if (!isNeo) return;
    const controller = new AbortController();
    apiGet("/api/space-data/neo-accessible", {
      query: { years: "2031", criterion: 1, limit: 10 },
      signal: controller.signal,
    }).then((r) => {
      if (controller.signal.aborted) return;
      setLoad(r.ok && r.data ? { status: "ready", data: r.data } : { status: "error" });
    });
    return () => controller.abort();
  }, [isNeo]);

  if (!mission || mission.scenarioId !== "neo-rendezvous") return null;
  const current = mission.trajectory;

  const use = (o: Option) =>
    setTrajectory(
      {
        provider: "jpl-mdesign",
        optionId: o.designation,
        departureDate: o.departureDate,
        arrivalDate: o.arrivalDate,
        timeOfFlightDays: o.timeOfFlightDays,
        c3Km2PerS2: o.c3Km2PerS2,
        departureVInfinityKmPerS: o.departureVInfinityKmPerS,
        arrivalVInfinityKmPerS: o.arrivalVInfinityKmPerS,
        missionDeltaVKmPerS: o.totalDeltaVKmPerS,
        rawSourceRef: o.sourceRef,
      },
      { bodyId: o.designation, name: o.name, bodyType: "asteroid", source: o.source },
    );

  return (
    <section data-testid="target-picker" aria-labelledby="target-picker-h" className="panel min-w-0 max-w-full space-y-3 p-4">
      <h2 id="target-picker-h" className="flex items-center gap-2 text-lg font-semibold">
        <Satellite aria-hidden className="h-4 w-4 text-accent-cyan" />
        Target and trajectory
      </h2>
      <p className="text-sm">
        Current: <span className="font-medium">{mission.destination.name}</span> · {current.provider} ·{" "}
        {current.departureDate} to {current.arrivalDate ?? "?"}
      </p>
      {load.status === "loading" ? (
        <p role="status" className="text-sm text-muted">
          Loading accessible near-Earth objects...
        </p>
      ) : load.status === "error" ? (
        <p className="text-sm text-accent-amber">Target data is unavailable; the scenario preset stays in use.</p>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <StatusPill tone={load.data.source.status === "live" ? "ok" : load.data.source.synthetic ? "warn" : "info"}>
              <span data-testid="jpl-source-badge" className="inline-flex items-center gap-1">
                <Database aria-hidden className="h-3 w-3" />
                {sourceLabel(load.data.source)}
              </span>
            </StatusPill>
            <span className="text-muted">{load.data.source.note}</span>
          </div>
          <div tabIndex={0} role="region" aria-label="Accessible targets (scrolls sideways)" className="relative w-full max-w-full overflow-x-auto rounded-xl border border-border">
            <table className="w-full min-w-[40rem] text-left text-sm">
              <thead className="text-xs text-muted">
                <tr>
                  <th scope="col" className="px-3 py-2 font-medium">Target</th>
                  <th scope="col" className="px-3 py-2 font-medium">Launch → arrival</th>
                  <th scope="col" className="px-3 py-2 font-medium">C3 (launch)</th>
                  <th scope="col" className="px-3 py-2 font-medium">v∞ dep / arr</th>
                  <th scope="col" className="px-3 py-2 font-medium">Total Δv (info)</th>
                  <th scope="col" className="px-3 py-2 font-medium">Source</th>
                  <th scope="col" className="px-3 py-2 font-medium"><span className="sr-only">Action</span></th>
                </tr>
              </thead>
              <tbody>
                {load.data.options.map((o) => {
                  const chosen = current.rawSourceRef === o.sourceRef;
                  return (
                    <tr key={o.sourceRef} data-testid={`target-option-${o.designation}`} className="border-t border-border/60">
                      <td className="px-3 py-2">{o.name}</td>
                      <td className="px-3 py-2 tabular-nums">
                        {o.departureDate} → {o.arrivalDate} ({formatNumber(o.timeOfFlightDays)} d)
                      </td>
                      <td className="px-3 py-2 tabular-nums">{formatNumber(o.c3Km2PerS2)} km²/s²</td>
                      <td className="px-3 py-2 tabular-nums">
                        {formatNumber(o.departureVInfinityKmPerS)} / {formatNumber(o.arrivalVInfinityKmPerS)} km/s
                      </td>
                      <td className="px-3 py-2 tabular-nums">{formatNumber(o.totalDeltaVKmPerS)} km/s</td>
                      <td className="px-3 py-2">
                        <FidelityBadge fidelity={o.source.fidelity} />
                      </td>
                      <td className="px-3 py-2">
                        {chosen ? (
                          <StatusPill tone="ok">In use</StatusPill>
                        ) : (
                          <button type="button" className={ACTION_CLASS} onClick={() => use(o)}>
                            Use this target
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-muted">
            C3 is launch energy from the rocket; it is never added to the spacecraft&apos;s delta-v. JPL&apos;s total
            Δv is shown for information; the spacecraft rendezvous burn comes from the scenario.
          </p>
        </>
      )}
    </section>
  );
}

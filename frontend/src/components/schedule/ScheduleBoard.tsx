"use client";

import { CalendarRange } from "lucide-react";
import { useEffect, useState } from "react";

import { FidelityBadge } from "@/components/common/FidelityBadge";
import { apiPost } from "@/lib/api-client";
import type { components } from "@/lib/api/schema";
import { formatFraction, formatNumber } from "@/lib/format";
import { useMissionStore } from "@/state/mission-store";

type ScheduleData = components["schemas"]["ScheduleData"];

/** Validated categorical slots 1-3 (dark steps), as in the Design Arena chart. */
const COLOR = { observation: "#3987e5", contact: "#199e70", buffer: "#d95926" } as const;
const DAY = 86400;
const W = 1000; // viewBox units across the time axis
const MIN_BLOCK = 4; // keep 4-hour observations visible on a months-long axis

const REASON: Record<string, string> = {
  INSTRUMENT_CONFLICT: "Instrument busy with another observation",
  ENERGY: "Needs more energy than the battery can give",
  POINTING: "Needs finer pointing than the attitude system gives",
  BUFFER_OVERFLOW_BEFORE_CONTACT: "Storage would overflow before the next contact",
  NO_CONTACT: "No usable contact afterwards; storage would overflow",
  PHASE: "Not allowed in this mission phase",
  THERMAL: "Thermal limit",
};

function bits(v: number): string {
  return `${formatNumber(v / 1e9)} Gbit`;
}

/**
 * Science/downlink schedule board (Task 6.6). Observations, ground contacts and onboard
 * storage on one time axis, from the backend's greedy scheduler. Display only.
 */
export function ScheduleBoard() {
  const missionId = useMissionStore((s) => s.mission?.missionId ?? null);
  const designRevision = useMissionStore((s) => s.designRevision);
  const [data, setData] = useState<ScheduleData | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const mission = useMissionStore.getState().mission;
    if (!missionId || !mission) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      apiPost(
        "/api/mission/schedule",
        { missionState: mission, acceptDataLoss: false },
        { signal: controller.signal },
      ).then((r) => {
        if (controller.signal.aborted || useMissionStore.getState().designRevision !== mission.designRevision) return;
        if (r.ok && r.data) {
          setData(r.data);
          setError(false);
        } else setError(true);
      });
    }, 350);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [missionId, designRevision]);

  if (!data) {
    return (
      <section data-testid="schedule-board" className="rounded-xl border border-border bg-surface/40 p-4 text-sm text-muted">
        {error ? "The schedule could not be built for this revision." : "Building the observation schedule..."}
      </section>
    );
  }

  const s = data.schedule;
  const times = [
    ...data.opportunities.flatMap((o) => [o.start, o.end]),
    ...data.contacts.flatMap((c) => [c.start, c.end]),
  ];
  const t0 = times.length ? Math.min(...times) : 0;
  const t1 = times.length ? Math.max(...times) : 1;
  const span = Math.max(t1 - t0, 1);
  const x = (t: number) => ((t - t0) / span) * W;
  const width = (a: number, b: number) => Math.max(MIN_BLOCK, x(b) - x(a));
  const accepted = new Set(s.accepted);
  const reasonOf = new Map(s.rejected.map((r) => [r.id, r.reasonCode]));
  const cap = data.bufferCapacityBits || 1;
  const sentBy = new Map(
    s.cycles.filter((c) => c.contactWindowId).map((c) => [c.contactWindowId as string, c.bufferBeforeBits - c.bufferAfterBits]),
  );
  const returned = [...sentBy.values()].reduce((a, b) => a + b, 0);
  const generated = data.opportunities.filter((o) => accepted.has(o.id)).reduce((a, o) => a + o.generatedDataBits, 0);
  const peak = Math.max(0, ...s.bufferTimeline.map((p) => p.bits));
  // Step line for storage use (0..1 of capacity), clipped to the axis window.
  const path = s.bufferTimeline
    .map((p, i) => {
      const px = Math.min(W, Math.max(0, x(Math.max(p.t, t0))));
      const py = 56 - (p.bits / cap) * 52;
      const prev = i > 0 ? 56 - (s.bufferTimeline[i - 1].bits / cap) * 52 : py;
      return i === 0 ? `M${px},${py}` : `L${px},${prev} L${px},${py}`;
    })
    .join(" ");

  const rows = [
    { key: "obs", label: "Observations" },
    { key: "contacts", label: "Ground contacts" },
    { key: "buffer", label: "Storage used" },
  ];

  return (
    <section
      aria-labelledby="schedule-title"
      data-testid="schedule-board"
      className="space-y-4 rounded-xl border border-border bg-surface/40 p-4"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h2 id="schedule-title" className="flex items-center gap-2 text-lg font-semibold">
            <CalendarRange aria-hidden className="h-5 w-5 text-accent-cyan" />
            Observation and downlink schedule
          </h2>
          <p className="max-w-3xl text-sm text-muted">
            Collecting data is only half the job: it has to fit in onboard storage until a ground contact sends it home.
            The scheduler keeps the most valuable observations that fit, and says why it dropped the rest.
          </p>
        </div>
        <FidelityBadge fidelity="derived" />
      </header>

      <dl className="grid gap-3 text-sm sm:grid-cols-4" data-testid="schedule-summary">
        <div className="rounded-lg border border-border bg-surface p-3">
          <dt className="text-xs text-muted">Observations kept</dt>
          <dd className="text-lg font-semibold">
            {s.accepted.length} of {data.opportunities.length}
          </dd>
        </div>
        <div className="rounded-lg border border-border bg-surface p-3">
          <dt className="text-xs text-muted">Data collected</dt>
          <dd className="text-lg font-semibold">{bits(generated)}</dd>
        </div>
        <div className="rounded-lg border border-border bg-surface p-3">
          <dt className="text-xs text-muted">Data returned to Earth</dt>
          <dd className="text-lg font-semibold">{bits(returned)}</dd>
        </div>
        <div className="rounded-lg border border-border bg-surface p-3">
          <dt className="text-xs text-muted">Peak storage use</dt>
          <dd className="text-lg font-semibold">{formatFraction(peak / cap)}</dd>
        </div>
      </dl>

      <figure className="space-y-2">
        <figcaption className="text-sm font-medium">
          Timeline, day {formatNumber(t0 / DAY)} to day {formatNumber(t1 / DAY)}
        </figcaption>
        <div className="grid grid-cols-[8rem_1fr] items-center gap-x-3 gap-y-2 text-xs">
          {rows.map((row) => (
            <div key={row.key} className="contents">
              <span className="text-muted">{row.label}</span>
              <svg
                viewBox={`0 0 ${W} 60`}
                preserveAspectRatio="none"
                className="h-12 w-full rounded bg-surface"
                role="img"
                aria-label={`${row.label} over time`}
              >
                {row.key === "obs"
                  ? data.opportunities.map((o) => {
                      const kept = accepted.has(o.id);
                      return (
                        <rect
                          key={o.id}
                          x={x(o.start)}
                          y={8}
                          width={width(o.start, o.end)}
                          height={44}
                          rx={2}
                          fill={kept ? COLOR.observation : "none"}
                          stroke={COLOR.observation}
                          strokeWidth={kept ? 0 : 2}
                          strokeDasharray={kept ? undefined : "4 3"}
                          vectorEffect="non-scaling-stroke"
                        >
                          <title>
                            {`${o.instrumentId}, day ${formatNumber(o.start / DAY)}: ${
                              kept ? "kept" : REASON[reasonOf.get(o.id) ?? ""] ?? "dropped"
                            }, ${bits(o.generatedDataBits)}`}
                          </title>
                        </rect>
                      );
                    })
                  : row.key === "contacts"
                    ? data.contacts.map((c) => {
                        const usable = c.linkMarginDb >= 0;
                        return (
                          <rect
                            key={c.id}
                            x={x(c.start)}
                            y={8}
                            width={width(c.start, c.end)}
                            height={44}
                            rx={2}
                            fill={usable ? COLOR.contact : "none"}
                            stroke={COLOR.contact}
                            strokeWidth={usable ? 0 : 2}
                            strokeDasharray={usable ? undefined : "4 3"}
                            vectorEffect="non-scaling-stroke"
                          >
                            <title>
                              {`Contact day ${formatNumber(c.start / DAY)}: ${
                                usable ? `sent ${bits(sentBy.get(c.id) ?? 0)}` : `link margin ${formatNumber(c.linkMarginDb)} dB, sends nothing`
                              }`}
                            </title>
                          </rect>
                        );
                      })
                    : (
                        <>
                          <line x1={0} x2={W} y1={4} y2={4} stroke="#8fa0b8" strokeDasharray="6 4" vectorEffect="non-scaling-stroke" />
                          <path d={path} fill="none" stroke={COLOR.buffer} strokeWidth={2} vectorEffect="non-scaling-stroke" />
                        </>
                      )}
              </svg>
            </div>
          ))}
        </div>
        <p className="text-xs text-muted">
          Solid blocks happen; dashed outlines are dropped observations or contacts that return nothing. The dashed line
          on the storage row is full capacity ({bits(cap)}). Hover a block for details.
        </p>
      </figure>

      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full min-w-[36rem] text-left text-sm" data-testid="schedule-table">
          <caption className="sr-only">Every planned observation and the scheduler&apos;s decision</caption>
          <thead className="bg-surface text-xs uppercase tracking-wide text-muted">
            <tr>
              <th scope="col" className="px-3 py-2 font-medium">Observation</th>
              <th scope="col" className="px-3 py-2 font-medium">Measurement</th>
              <th scope="col" className="px-3 py-2 font-medium">Data</th>
              <th scope="col" className="px-3 py-2 font-medium">Decision</th>
            </tr>
          </thead>
          <tbody>
            {data.opportunities.map((o) => (
              <tr key={o.id} className="border-t border-border" data-testid={`schedule-row-${o.id}`}>
                <td className="px-3 py-2">
                  <span className="font-mono text-xs">{o.instrumentId}</span>
                  <span className="block text-xs text-muted">day {formatNumber(o.start / DAY)}</span>
                </td>
                <td className="px-3 py-2 font-mono text-xs">{data.measurementOf[o.id]}</td>
                <td className="px-3 py-2 font-mono text-xs">{bits(o.generatedDataBits)}</td>
                <td className="px-3 py-2">
                  {accepted.has(o.id) ? (
                    <span className="text-accent-cyan">Kept</span>
                  ) : (
                    <span className="text-accent-amber">Dropped: {REASON[reasonOf.get(o.id) ?? ""] ?? reasonOf.get(o.id)}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted" data-testid="schedule-algorithm">
        {data.algorithm}
      </p>
    </section>
  );
}

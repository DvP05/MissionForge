"use client";

import { ArrowDown, ArrowRight, ArrowUp, Minus } from "lucide-react";
import { CartesianGrid, Line, LineChart, ReferenceLine, XAxis, YAxis } from "recharts";

import { FidelityBadge } from "@/components/common/FidelityBadge";
import { formatFraction, formatNumber, humanize } from "@/lib/format";
import {
  channelIds,
  channelSnapshots,
  trendOf,
  triggerThresholds,
  type MissionEvent,
  type TelemetrySample,
  type Trend,
} from "./playback";

const TREND: Record<Trend, { label: string; Icon: typeof ArrowUp }> = {
  rising: { label: "Rising", Icon: ArrowUp },
  falling: { label: "Falling", Icon: ArrowDown },
  steady: { label: "Steady", Icon: ArrowRight },
  "no-trend": { label: "No earlier sample", Icon: Minus },
};

function show(sample: TelemetrySample): string {
  return sample.unit === "fraction" ? formatFraction(sample.value) : `${formatNumber(sample.value)} ${sample.unit}`;
}

const unitLabel = (u: string) => (u === "fraction" ? "fraction (0 to 1)" : u);

export function TelemetryCards({ samples, day }: { samples: TelemetrySample[]; day: number }) {
  const snaps = channelSnapshots(samples, day);
  return (
    <ul aria-label="Telemetry" className="grid gap-2 sm:grid-cols-2">
      {channelIds(samples).map((ch) => {
        const snap = snaps.get(ch);
        const T = snap ? TREND[trendOf(snap)] : null;
        return (
          <li
            key={ch}
            data-testid={`telemetry-card-${ch}`}
            className="min-w-0 space-y-1 rounded-lg border border-border p-3"
          >
            <p className="text-xs text-muted">{humanize(ch)}</p>
            {snap && T ? (
              <>
                <p className="text-lg font-semibold tabular-nums">{show(snap.latest)}</p>
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <FidelityBadge fidelity={snap.latest.fidelity} />
                  <span data-testid="trend" className="inline-flex items-center gap-1 text-muted">
                    <T.Icon aria-hidden className="h-3.5 w-3.5" />
                    {T.label}
                  </span>
                </div>
                <p className="text-xs text-muted">Sampled on day {snap.latest.missionDay.toFixed(1)}</p>
              </>
            ) : (
              <p className="text-sm text-muted">— no sample yet</p>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export function TelemetryCharts({
  samples,
  events,
  day,
  duration,
}: {
  samples: TelemetrySample[];
  events: MissionEvent[];
  day: number;
  duration: number;
}) {
  const thresholds = triggerThresholds(events);
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {channelIds(samples).map((ch) => {
        const own = samples.filter((s) => s.channel === ch);
        const unit = own[0]?.unit ?? "";
        const shown = own.filter((s) => s.missionDay <= day).map((s) => ({ day: s.missionDay, value: s.value }));
        const thr = thresholds[ch];
        return (
          <figure
            key={ch}
            data-testid={`telemetry-chart-${ch}`}
            data-x-axis="mission-day"
            data-x-domain={`0,${duration}`}
            data-unit={unit}
            className="min-w-0 space-y-1 rounded-lg border border-border p-3"
          >
            <figcaption className="text-sm font-medium">
              {humanize(ch)} <span data-testid="chart-unit" className="font-normal text-muted">[{unitLabel(unit)}]</span>
            </figcaption>
            <div role="img" aria-label={`${humanize(ch)} in ${unitLabel(unit)} against mission day`} className="overflow-hidden">
              <LineChart
                width={320}
                height={150}
                responsive
                style={{ width: "100%", maxWidth: "100%", height: 150 }}
                data={shown}
                margin={{ top: 8, right: 12, bottom: 4, left: 0 }}
              >
                <CartesianGrid stroke="#243044" strokeDasharray="3 3" />
                <XAxis dataKey="day" type="number" domain={[0, duration]} tick={{ fill: "#8fa0b8", fontSize: 11 }} />
                <YAxis width={44} tick={{ fill: "#8fa0b8", fontSize: 11 }} domain={["auto", "auto"]} />
                <Line type="linear" dataKey="value" stroke="#22d3ee" dot={{ r: 2 }} isAnimationActive={false} />
                {thr ? (
                  <ReferenceLine y={thr.value} stroke="#fbbf24" strokeDasharray="4 2" label={{ value: `threshold ${thr.value} ${unit}`, fill: "#fbbf24", fontSize: 10 }} />
                ) : null}
              </LineChart>
            </div>
            <p className="text-xs text-muted">Mission day (d). {thr ? `Dashed line: threshold stated by event ${thr.eventId}.` : "No threshold stated by an event trigger."}</p>
          </figure>
        );
      })}
    </div>
  );
}

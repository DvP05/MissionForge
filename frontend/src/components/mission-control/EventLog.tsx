"use client";

import { CircleAlert, Info, TriangleAlert, type LucideIcon } from "lucide-react";
import { useState } from "react";

import type { DecisionRecord, MissionEvent } from "./playback";

const SEVERITY: Record<MissionEvent["severity"], { Icon: LucideIcon; tone: string }> = {
  info: { Icon: Info, tone: "text-accent-cyan" },
  warning: { Icon: TriangleAlert, tone: "text-accent-amber" },
  critical: { Icon: CircleAlert, tone: "text-accent-red" },
};

const TYPES = ["milestone", "telemetry", "anomaly", "decision", "science", "downlink"] as const;
const SEVERITIES = ["info", "warning", "critical"] as const;
const SELECT = "min-h-11 rounded-lg border border-border bg-surface px-2 text-sm";

/** The "Why this happened" text of an event: its description plus the trigger values. */
function EventItem({ event, decision }: { event: MissionEvent; decision: DecisionRecord | undefined }) {
  const { Icon, tone } = SEVERITY[event.severity];
  const choice = decision ? event.choices.find((c) => c.id === decision.choiceId) : undefined;
  return (
    <li data-testid={`event-item-${event.id}`} className="min-w-0 space-y-1 border-b border-border py-2 text-sm last:border-b-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="break-all font-mono text-xs">{event.id}</span>
        <span data-testid="event-day" className="text-xs tabular-nums text-muted">
          Day {event.missionDay.toFixed(1)}
        </span>
        <span data-testid="event-severity" className={`inline-flex items-center gap-1 text-xs font-medium ${tone}`}>
          <Icon aria-hidden className="h-3.5 w-3.5" />
          {event.severity}
        </span>
        <span className="text-xs text-muted">{event.type}</span>
      </div>
      <p className="font-medium">{event.title}</p>
      {decision ? (
        <p data-testid="decision-maker" className="text-xs">
          Decision: {choice?.label ?? decision.choiceId} — decided by{" "}
          {decision.decisionMaker === "player" ? "player" : `${decision.decisionMaker} (default, no player choice)`}
        </p>
      ) : null}
      <details data-testid="event-why" className="text-xs text-muted">
        <summary className="cursor-pointer text-foreground">Why this happened</summary>
        <p className="mt-1">{event.description}</p>
        <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
          {Object.entries(event.trigger).map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="font-mono">{k}</dt>
              <dd className="break-all">{String(v)}</dd>
            </div>
          ))}
        </dl>
      </details>
    </li>
  );
}

export function EventLog({ events, decisions }: { events: MissionEvent[]; decisions: DecisionRecord[] }) {
  const [type, setType] = useState("all");
  const [severity, setSeverity] = useState("all");
  const shown = events
    .filter((e) => (type === "all" || e.type === type) && (severity === "all" || e.severity === severity))
    .reverse();
  return (
    <section aria-label="Event log" data-testid="event-log" className="min-w-0 space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="mr-auto text-base font-semibold">Event log</h2>
        <label className="text-xs text-muted">
          Type{" "}
          <select data-testid="filter-type" value={type} onChange={(e) => setType(e.target.value)} className={SELECT}>
            <option value="all">All</option>
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-muted">
          Severity{" "}
          <select data-testid="filter-severity" value={severity} onChange={(e) => setSeverity(e.target.value)} className={SELECT}>
            <option value="all">All</option>
            {SEVERITIES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
      </div>
      {shown.length === 0 ? (
        <p className="text-sm text-muted">No events match yet at this point of the mission.</p>
      ) : (
        <ul className="max-h-[32rem] overflow-y-auto rounded-lg border border-border px-3">
          {shown.map((e) => (
            <EventItem key={e.id} event={e} decision={decisions.find((d) => d.eventId === e.id)} />
          ))}
        </ul>
      )}
    </section>
  );
}

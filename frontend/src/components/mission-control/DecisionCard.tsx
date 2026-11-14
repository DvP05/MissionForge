"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { apiPost } from "@/lib/api-client";
import { formatNumber, humanize } from "@/lib/format";
import { useRunStore } from "@/state/run-store";
import type { MissionEvent, TelemetrySample } from "./playback";

/** The backend description minus its option list (the options are rendered as choices). */
function situationText(event: MissionEvent): string {
  const cut = event.description.indexOf(" Options: ");
  return cut >= 0 ? event.description.slice(0, cut) : event.description;
}

/**
 * Pauses playback and requires a choice. Choosing posts the decision; the backend
 * returns a NEW run and the UI continues on it at the same mission day.
 */
export function DecisionCard({
  event,
  runId,
  telemetry,
}: {
  event: MissionEvent;
  runId: string;
  telemetry: TelemetrySample[];
}) {
  const router = useRouter();
  const [choice, setChoice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isScenario = event.trigger["source"] === "scenario-event";
  const thresholdDb = event.trigger["threshold_db"];
  const link = [...telemetry].reverse().find((s) => s.channel === "link_margin_db" && s.missionDay <= event.missionDay);

  async function confirm() {
    if (!choice || busy) return;
    setBusy(true);
    setError(null);
    const res = await apiPost(
      "/api/mission/run/{run_id}/decision",
      { eventId: event.id, choiceId: choice },
      { pathParams: { run_id: runId } },
    );
    if (res.ok && res.data) {
      useRunStore.getState().putRun(res.data);
      router.push(`/control/${res.data.run.runId}?day=${event.missionDay}`);
      return;
    }
    setBusy(false);
    setError(res.error?.message ?? "The decision could not be applied.");
  }

  return (
    <section
      data-testid="decision-card"
      aria-labelledby="decision-title"
      className="space-y-3 rounded-lg border border-accent-amber/60 bg-accent-amber/5 p-4"
    >
      <div className="space-y-1">
        <p className="text-xs font-medium uppercase tracking-wide text-accent-amber">
          Decision required — day {event.missionDay.toFixed(1)} — playback paused
        </p>
        <h2 id="decision-title" className="text-lg font-semibold">
          {event.title}
        </h2>
        <p data-testid="decision-kind" className="text-xs text-muted">
          {isScenario
            ? "Scenario uncertainty: the day is drawn from a seeded stream; the effects of each choice are deterministic."
            : "Deterministic rule: triggered by a value in your design."}
        </p>
      </div>
      <p data-testid="decision-situation" className="text-sm">
        {situationText(event)}
      </p>
      <dl data-testid="decision-trigger" className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs text-muted">
        {Object.entries(event.trigger).map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="font-mono">{k}</dt>
            <dd className="break-all">{String(v)}</dd>
          </div>
        ))}
        {typeof thresholdDb === "number" && link ? (
          <div className="contents">
            <dt className="font-mono">link margin now</dt>
            <dd>
              {formatNumber(link.value)} dB against threshold {thresholdDb} dB
            </dd>
          </div>
        ) : null}
      </dl>
      <fieldset className="space-y-2">
        <legend className="mb-1 text-sm font-medium">Choose one option</legend>
        {event.choices.map((c) => (
          <label
            key={c.id}
            data-testid={`choice-${c.id}`}
            className={`flex min-h-11 cursor-pointer gap-3 rounded-lg border p-3 text-sm ${
              choice === c.id ? "border-accent-cyan bg-accent-cyan/10" : "border-border"
            }`}
          >
            <input
              type="radio"
              name={`decision-${event.id}`}
              value={c.id}
              checked={choice === c.id}
              onChange={() => setChoice(c.id)}
              className="mt-1 h-4 w-4 shrink-0 accent-cyan-400"
            />
            <span className="min-w-0 space-y-1">
              <span className="block font-medium">{c.label}</span>
              <span className="block text-muted">{c.tradeoff}</span>
              {Object.keys(c.effects ?? {}).length > 0 ? (
                <span className="block text-xs text-muted">
                  Effects:{" "}
                  {Object.entries(c.effects ?? {})
                    .map(([k, v]) => `${humanize(k)} ${v}`)
                    .join("; ")}
                </span>
              ) : (
                <span className="block text-xs text-muted">Effects: none beyond the plan.</span>
              )}
            </span>
          </label>
        ))}
      </fieldset>
      {error ? (
        <p role="alert" className="text-sm text-red-300">
          {error}
        </p>
      ) : null}
      <button
        type="button"
        data-testid="confirm-decision"
        disabled={!choice || busy}
        onClick={confirm}
        className="inline-flex min-h-11 items-center rounded-lg border border-accent-cyan/60 px-4 text-sm font-medium text-accent-cyan hover:bg-accent-cyan/10 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {busy ? "Applying decision…" : "Confirm decision"}
      </button>
    </section>
  );
}

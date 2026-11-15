"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { apiPost } from "@/lib/api-client";
import { formatNumber, humanize } from "@/lib/format";
import { useRunStore } from "@/state/run-store";
import type { Authority } from "./authority";
import type { DesignLimit, MissionEvent, TelemetrySample } from "./playback";

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
  linkLimit,
  authority = null,
}: {
  event: MissionEvent;
  runId: string;
  telemetry: TelemetrySample[];
  linkLimit: DesignLimit | null;
  authority?: Authority | null;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  // The card appears while the focused Play button becomes disabled: move focus to the card.
  useEffect(() => heading.current?.focus(), []);
  const router = useRouter();
  const [choice, setChoice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isScenario = event.trigger["source"] === "scenario-event";
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
      className="space-y-3 rounded-xl border-2 border-accent-amber/70 bg-accent-amber/[0.07] p-5 shadow-[0_0_32px_-12px_var(--amber)]"
    >
      <div className="space-y-1">
        <p role="alert" className="text-xs font-medium uppercase tracking-wide text-accent-amber">
          Decision required — day {event.missionDay.toFixed(1)} — playback paused
        </p>
        <h2 id="decision-title" ref={heading} tabIndex={-1} className="text-lg font-semibold outline-offset-4">
          {event.title}
        </h2>
        <p data-testid="decision-kind" className="text-xs text-muted">
          {isScenario
            ? "Scenario uncertainty: the day is drawn from a seeded stream; the effects of each choice are deterministic."
            : "Deterministic rule: triggered by a value in your design."}
        </p>
      </div>
      {authority ? (
        <p data-testid="decision-authority" className="text-xs">
          {authority.mode === "onboard"
            ? `Communication blackout: Earth cannot command the spacecraft now${
                authority.untilDays !== null ? ` (next contact in ${formatNumber(authority.untilDays)} d)` : ""
              }. Your choice selects one of the stored contingency responses, which the spacecraft executes on board.`
            : "Ground contact: your choice is uplinked as a ground command during this pass."}
        </p>
      ) : null}
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
        {linkLimit ? (
          <div className="contents" data-testid="decision-link-margin">
            <dt className="font-mono">link margin</dt>
            <dd>
              {link ? `${formatNumber(link.value)} dB (day ${link.missionDay.toFixed(1)})` : "not sampled before this day"};
              design-time limit {formatNumber(linkLimit.value)} {linkLimit.unit} ({linkLimit.provenance.fidelity})
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
        <p role="alert" className="text-sm text-accent-red">
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

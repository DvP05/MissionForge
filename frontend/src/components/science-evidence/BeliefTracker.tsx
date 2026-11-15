"use client";

import { FlaskConical, RotateCcw, Telescope } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { FidelityBadge } from "@/components/common/FidelityBadge";
import { ACTION_CLASS } from "@/components/common/States";
import { apiPost } from "@/lib/api-client";
import type { components } from "@/lib/api/schema";
import { formatFraction, formatNumber } from "@/lib/format";
import { useMissionStore } from "@/state/mission-store";

type BeliefData = components["schemas"]["BeliefData"];
type ObservationIn = components["schemas"]["ObservationIn"];

/** Single-series bar colour: the validated categorical slot 1 (dark step). */
const BAR = "#3987e5";

function words(id: string): string {
  return id.replace(/-/g, " ");
}

/**
 * Science belief tracker (Task 6.4). The spacecraft holds competing hypotheses about the
 * target and updates them with Bayes' rule after each observation. The backend draws each
 * outcome from a hidden, seeded scenario truth that is never sent to the browser.
 */
export function BeliefTracker() {
  const mission = useMissionStore((s) => s.mission);
  const designRevision = useMissionStore((s) => s.designRevision);
  const [data, setData] = useState<BeliefData | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "unavailable" | "error">("loading");
  const [busy, setBusy] = useState(false);
  const history = useRef<ObservationIn[]>([]);

  const request = useCallback(async (observeWith: string | null) => {
    const m = useMissionStore.getState().mission;
    if (!m) return;
    setBusy(true);
    const r = await apiPost("/api/science/belief", {
      missionState: m,
      history: history.current,
      observeWith,
    });
    setBusy(false);
    if (r.ok && r.data) {
      history.current = r.data.history;
      setData(r.data);
      setStatus("ready");
    } else {
      setStatus(r.error?.code === "SCIENCE_MODEL_UNAVAILABLE" ? "unavailable" : "error");
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => void request(null), 0);
    return () => clearTimeout(timer);
  }, [request, designRevision, mission?.missionId]);

  if (!mission) return null;
  if (status === "unavailable") {
    return (
      <p data-testid="belief-unavailable" className="rounded-xl border border-dashed border-border p-4 text-sm text-muted">
        The science hypothesis tracker is available for the asteroid scenario first.
      </p>
    );
  }

  const label = new Map(data?.hypotheses.map((h) => [h.id, h.label]) ?? []);
  const prior = new Map(data?.hypotheses.map((h) => [h.id, h.priorProbability]) ?? []);
  const maxEntropy = data ? Math.log2(Math.max(2, data.hypotheses.length)) : 1;
  const last = data?.lastOutcome ?? null;
  const lastTable = last
    ? data?.likelihoods.find((t) => t.instrumentId === last.instrumentId && t.outcomeId === last.outcomeId)
    : undefined;

  return (
    <section
      aria-labelledby="belief-title"
      data-testid="belief-tracker"
      className="space-y-4 rounded-xl border border-border bg-surface/40 p-4"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h2 id="belief-title" className="flex items-center gap-2 text-lg font-semibold">
            <FlaskConical aria-hidden className="h-5 w-5 text-accent-cyan" />
            What is the asteroid made of?
          </h2>
          <p className="max-w-3xl text-sm text-muted">
            Scientists start with competing ideas. Each observation makes some ideas more likely and others less, using
            Bayes&apos; rule. Pick the observation that should teach you the most, then see how the odds move.
          </p>
        </div>
        <FidelityBadge fidelity="gameplay-estimate" />
      </header>

      {status === "error" ? (
        <p role="alert" className="text-sm text-accent-red">
          The belief could not be updated.{" "}
          <button type="button" className="underline" onClick={() => void request(null)}>
            Retry
          </button>
        </p>
      ) : null}
      {!data ? (
        status === "loading" ? (
          <p role="status" className="text-sm text-muted">
            Loading hypotheses...
          </p>
        ) : null
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-3">
            <h3 className="text-sm font-semibold">Current belief (after {data.history.length} observations)</h3>
            <ul className="space-y-3" data-testid="belief-bars">
              {data.belief.hypotheses.map((h) => (
                <li key={h.hypothesisId}>
                  <div className="flex justify-between text-sm">
                    <span>{label.get(h.hypothesisId) ?? h.hypothesisId}</span>
                    <span className="font-mono text-xs" data-testid={`belief-p-${h.hypothesisId}`}>
                      {formatFraction(h.probability)}
                    </span>
                  </div>
                  <div className="mt-1 h-2.5 w-full rounded-sm bg-border" aria-hidden>
                    <div className="h-2.5 rounded-sm" style={{ width: `${h.probability * 100}%`, background: BAR }} />
                  </div>
                  <p className="text-xs text-muted">Started at {formatFraction(prior.get(h.hypothesisId) ?? 0)}</p>
                </li>
              ))}
            </ul>
            <p className="text-sm">
              Remaining uncertainty: <span className="font-mono">{formatNumber(data.belief.entropyBits)} bits</span>{" "}
              <span className="text-muted">(maximum {formatNumber(maxEntropy)}, 0 means certain)</span>
            </p>
            {last ? (
              <div data-testid="belief-last" className="rounded-lg border border-border bg-surface p-3 text-sm">
                <p>
                  Latest observation: <span className="font-medium">{words(last.outcomeId)}</span> from{" "}
                  <span className="font-mono text-xs">{last.instrumentId}</span>
                </p>
                {lastTable ? (
                  <p className="mt-1 text-xs text-muted">
                    How likely that result is under each idea:{" "}
                    {Object.entries(lastTable.likelihoodByHypothesis)
                      .map(([h, p]) => `${label.get(h) ?? h} ${formatFraction(p)}`)
                      .join(", ")}
                    . Ideas that predicted it gain probability.
                  </p>
                ) : null}
                <p className="mt-1 text-xs text-muted">
                  Collected on board. Whether it reaches Earth depends on the downlink plan (mission simulation).
                </p>
              </div>
            ) : null}
          </div>

          <div className="space-y-3">
            <h3 className="flex items-center gap-2 text-sm font-semibold">
              <Telescope aria-hidden className="h-4 w-4" />
              What to observe next
            </h3>
            {data.nextObservations.length === 0 ? (
              <p className="text-sm text-muted">No instrument on this spacecraft can test these ideas.</p>
            ) : (
              <ol className="space-y-2" data-testid="belief-next">
                {data.nextObservations.map((n, i) => (
                  <li key={n.instrumentId} className="rounded-lg border border-border bg-surface p-3 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span>
                        {i === 0 ? <span className="mr-1 text-accent-cyan">Best:</span> : null}
                        <span className="font-mono text-xs">{n.instrumentId}</span>
                      </span>
                      <span className="text-xs text-muted">
                        expected to remove {formatNumber(n.expectedInformationGainBits)} bits
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-muted">
                      Possible results:{" "}
                      {Object.entries(n.outcomeProbabilities)
                        .map(([o, p]) => `${words(o)} ${formatFraction(p)}`)
                        .join(", ")}
                    </p>
                    <button
                      type="button"
                      data-testid={`belief-observe-${n.instrumentId}`}
                      disabled={busy}
                      onClick={() => void request(n.instrumentId)}
                      className={`${ACTION_CLASS} mt-2 disabled:opacity-50`}
                    >
                      Observe
                    </button>
                  </li>
                ))}
              </ol>
            )}
            {data.history.length > 0 ? (
              <button
                type="button"
                onClick={() => {
                  history.current = [];
                  void request(null);
                }}
                className="inline-flex items-center gap-1 text-xs text-muted hover:text-foreground"
              >
                <RotateCcw aria-hidden className="h-3 w-3" /> Start over
              </button>
            ) : null}
          </div>
        </div>
      )}
      {data ? (
        <p className="text-xs text-muted" data-testid="belief-disclaimer">
          {data.disclaimer} Model {data.modelVersion}.
        </p>
      ) : null}
    </section>
  );
}

"use client";

import Link from "next/link";

import { ExperimentalBadge } from "@/components/common/ExperimentalBadge";
import { PHASE_LABEL } from "@/components/mission-control/playback";
import { formatFraction } from "@/lib/format";
import type { RunData } from "@/lib/persistence/run-cache";
import { MarginsChart } from "./MarginsChart";

const H2 = "text-lg font-semibold";
const OUTCOME = { success: "Success", partial: "Partial success", failure: "Failure", terminated: "Mission terminated" } as const;

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section data-testid={id} aria-labelledby={`${id}-h`} className="space-y-2">
      <h2 id={`${id}-h`} className={H2}>
        {title}
      </h2>
      {children}
    </section>
  );
}

function ListOrNone({ items, none, ordered }: { items: string[]; none: string; ordered?: boolean }) {
  if (items.length === 0) return <p className="text-sm text-muted">{none}</p>;
  const Tag = ordered ? "ol" : "ul";
  return (
    <Tag className="space-y-1 text-sm">
      {items.map((t, i) => (
        <li key={i} className="break-words">
          {ordered ? <span className="font-medium">Rank {i + 1}: </span> : null}
          {t}
        </li>
      ))}
    </Tag>
  );
}

/** Post-mission review (prod 8.6). Everything shown is a field of the stored run. */
export function ReviewPage({ data }: { data: RunData }) {
  const run = data.run;
  const report = run.finalReport;
  const titleOf = (id: string) => run.inputSnapshot.scienceObjectives.find((o) => o.id === id)?.title ?? id;
  const achieved = run.scienceOutcomes.filter((o) => o.status === "achieved").length;
  const timeline = [
    ...run.phaseTransitions.map((t) => ({ day: t.missionDay, key: `p-${t.phase}`, text: `Phase: ${PHASE_LABEL[t.phase]}`, id: null as string | null })),
    ...run.events
      .filter((e) => e.type !== "milestone" && e.type !== "downlink" && e.type !== "telemetry")
      .map((e) => ({ day: e.missionDay, key: `e-${e.id}`, text: `${e.title} (${e.severity})`, id: e.id })),
  ].sort((a, b) => a.day - b.day);

  return (
    <article data-testid="review-page" className="space-y-8">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Mission review</h1>
        <p className="break-all font-mono text-xs text-muted">Run {run.runId} · seed {run.seed} · engine {run.engineVersion}</p>
        {run.experimental ? <ExperimentalBadge /> : null}
        <Link href={`/control/${run.runId}`} className="inline-flex min-h-11 items-center rounded-lg border border-border px-4 text-sm hover:text-accent-cyan">
          Back to mission control
        </Link>
      </header>

      <Section id="review-outcome" title="Outcome">
        <p className="text-xl font-semibold">{OUTCOME[report.outcome]}</p>
        <p className="text-sm">{report.summary}</p>
        <p className="text-sm text-muted">
          {achieved} of {run.scienceOutcomes.length} objectives achieved. Total score {report.score.total.toFixed(1)} of 100.
        </p>
      </Section>

      <Section id="review-objectives" title="Science objectives">
        {run.scienceOutcomes.length === 0 ? (
          <p className="text-sm text-muted">No objective outcomes were produced for this run.</p>
        ) : (
          <ul className="space-y-2">
            {run.scienceOutcomes.map((o) => (
              <li key={o.objectiveId} className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-border p-3 text-sm">
                <span className="min-w-0 break-words font-medium">{titleOf(o.objectiveId)}</span>
                <span data-testid={`objective-status-${o.objectiveId}`} className="rounded-full border border-border px-2.5 py-0.5 text-xs font-medium">
                  {o.status === "achieved" ? "Achieved" : o.status === "partial" ? "Partial" : "Missed"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section id="review-science" title="Science collected and returned">
        <p className="text-sm text-muted">Collected data is not the same as data returned to Earth; only returned data counts toward the objective.</p>
        <table className="w-full text-left text-sm">
          <thead className="text-xs text-muted">
            <tr>
              <th className="py-1 pr-3 font-normal">Objective</th>
              <th className="py-1 pr-3 font-normal">Collected</th>
              <th className="py-1 font-normal">Returned</th>
            </tr>
          </thead>
          <tbody>
            {run.scienceOutcomes.map((o) => (
              <tr key={o.objectiveId} className="border-t border-border align-top">
                <td className="min-w-0 break-words py-1 pr-3">{titleOf(o.objectiveId)}</td>
                <td className="py-1 pr-3 tabular-nums">{formatFraction(o.collectedFraction)}</td>
                <td className="py-1 tabular-nums">{formatFraction(o.returnedFraction)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <MarginsChart analysis={data.analysis} />

      <Section id="review-timeline" title="Operations timeline">
        <ol className="space-y-1 text-sm">
          {timeline.map((t) => (
            <li key={t.key} className="break-words">
              <span className="tabular-nums text-muted">Day {t.day.toFixed(1)} · </span>
              {t.id ? <span className="font-mono text-xs">{t.id} · </span> : null}
              {t.text}
            </li>
          ))}
        </ol>
      </Section>

      <Section id="review-decisions" title="Decisions">
        {run.decisions.length === 0 ? (
          <p className="text-sm text-muted">No decision events occurred in this run.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {run.decisions.map((d) => {
              const event = run.events.find((e) => e.id === d.eventId);
              const choice = event?.choices.find((c) => c.id === d.choiceId);
              return (
                <li key={d.eventId} className="break-words rounded-lg border border-border p-3">
                  <span className="font-medium">{event?.title ?? d.eventId}</span> (day {d.missionDay.toFixed(1)}): {choice?.label ?? d.choiceId}.
                  Decided by {d.decisionMaker === "player" ? "player" : `${d.decisionMaker} (default, no player choice)`}.
                </li>
              );
            })}
          </ul>
        )}
      </Section>

      <Section id="review-root-causes" title="Root causes">
        <ListOrNone ordered items={report.rootCauses} none="No root causes were recorded." />
      </Section>

      <Section id="review-counterfactuals" title="Counterfactuals">
        <ListOrNone items={report.counterfactuals} none="No counterfactual computed for this run." />
      </Section>

      <Section id="review-limitations" title="Data limitations">
        <ListOrNone items={report.limitations} none="No limitations were reported." />
      </Section>

      <Section id="review-score" title="Score">
        <p className="text-sm">Total {report.score.total.toFixed(1)} of 100</p>
        <ul className="space-y-2">
          {report.score.dimensions.map((d) => (
            <li key={d.id} data-testid={`score-dimension-${d.id}`} className="rounded-lg border border-border p-3 text-sm">
              <p className="font-medium">
                {d.id.replace(/-/g, " ")} <span className="font-normal text-muted">· weight {d.weight}</span>
              </p>
              <p className="tabular-nums">Score {d.score.toFixed(1)} of 100</p>
              <p className="text-xs text-muted">{d.explanation}</p>
            </li>
          ))}
        </ul>
      </Section>
    </article>
  );
}

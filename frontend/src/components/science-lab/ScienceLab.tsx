"use client";

import { ArrowRight, FlaskConical, Telescope } from "lucide-react";
import { useEffect, useState } from "react";

import { ComponentChangeDialog } from "@/components/architect/ComponentChangeDialog";
import { requestChange } from "@/components/architect/component-actions";
import { EngStatusChip } from "@/components/architect/EngStatusChip";
import { useCatalog } from "@/components/architect/useCatalog";
import type { CatalogComponent } from "@/components/architect/catalog-helpers";
import { StatusPill } from "@/components/common/StatusPill";
import { ErrorState, LoadingState } from "@/components/common/States";
import { SpacecraftStage } from "@/components/spacecraft3d/SpacecraftStage";
import { useAnalysis } from "@/hooks/useAnalysis";
import { formatFraction, formatNumber, formatQuantity, humanize } from "@/lib/format";
import { useArchitectUi } from "@/state/architect-ui-store";
import { useMissionStore, type MissionState, type ScienceObjective } from "@/state/mission-store";

type Measurement = ScienceObjective["requiredMeasurements"][number];

const short = (n: string) => n.replace(/^Archetype:\s*/, "");

/** Instruments that provide a capability: installed first, then catalogue candidates. */
function providers(capability: string, mission: MissionState, index: Map<string, CatalogComponent>) {
  const all = [...index.values()].filter((c) => c.category === "instrument" && (c.capabilities ?? []).includes(capability));
  const installed = all.filter((c) => mission.architecture.instrumentIds.includes(c.id));
  const candidates = all.filter((c) => !mission.architecture.instrumentIds.includes(c.id));
  return { installed, candidates };
}

function Consequence({ c }: { c: CatalogComponent }) {
  const keys = ["mass", "power_w", "data_rate"];
  return (
    <span className="font-mono text-[11px] text-muted">
      {keys
        .filter((k) => c.parameters[k])
        .map((k) => `${humanize(k)} ${formatQuantity(c.parameters[k])}`)
        .join(" · ")}
    </span>
  );
}

/**
 * Science Laboratory (front_design.md 4.C). For each objective it shows the chain
 * objective -> required measurement -> instrument capability -> engineering consequence ->
 * expected return. Coverage and return come only from the backend analysis of the current
 * revision; instrument figures are catalogue values. Selecting an objective highlights the
 * instruments that serve it in the spacecraft view.
 */
export function ScienceLab() {
  const mission = useMissionStore((s) => s.mission);
  const analysis = useMissionStore((s) => s.analysis);
  const analysisRevision = useMissionStore((s) => s.analysisRevision);
  const status = useMissionStore((s) => s.status);
  useAnalysis();
  const { catalog, retry } = useCatalog();
  const [activeId, setActiveId] = useState<string | null>(null);
  const highlight = useArchitectUi((s) => s.highlight);

  // The highlight follows the canonical design: recomputed whenever the instruments change.
  const instrumentKey = mission?.architecture.instrumentIds.join(",") ?? "";
  const catalogIndex = catalog.kind === "ready" ? catalog.index : null;
  useEffect(() => {
    const o = mission?.scienceObjectives.find((x) => x.id === activeId);
    if (!o || !mission || !catalogIndex) {
      highlight([], null);
      return;
    }
    const ids = [...new Set(o.requiredMeasurements.flatMap((m) => providers(m.instrumentCapability, mission, catalogIndex).installed.map((c) => c.id)))];
    highlight(ids.length ? ids : ["__none__"], ids.length ? `instruments serving "${o.title}"` : `no installed instrument serves "${o.title}"`);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- instrumentKey stands for the instrument list
  }, [activeId, instrumentKey, catalogIndex, highlight]);
  useEffect(() => () => highlight([], null), [highlight]);

  if (!mission) return <LoadingState label="Loading mission" />;
  if (catalog.kind === "loading") return <LoadingState label="Loading instrument catalogue" />;
  if (catalog.kind === "error") return <ErrorState title="Catalogue unavailable" message={catalog.message} onRetry={retry} />;
  const index = catalog.index;
  const current = analysis !== null && analysisRevision === mission.designRevision;
  const freshness = status === "calculating" ? "ANALYSING" : analysis && !current ? "STALE" : null;
  const missing = new Set(analysis?.science.missingRequirements ?? []);

  const focus = (o: ScienceObjective) => setActiveId((id) => (id === o.id ? null : o.id));

  const install = (c: CatalogComponent, opener: HTMLElement) => requestChange(index, "instrument", c.id, opener);

  return (
    <div className="space-y-4" data-testid="science-lab">
      <ComponentChangeDialog index={index} />
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-xl font-semibold">
          <FlaskConical aria-hidden className="h-5 w-5 text-accent-violet" /> Science laboratory
        </h2>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
          {analysis ? (
            <>
              <span>
                Mission-wide: collected {formatFraction(analysis.science.collectedFraction)} · returned{" "}
                {formatFraction(analysis.science.returnedFraction)} · coverage score {formatNumber(analysis.science.coverageScore)} %
              </span>
              <span>(revision {analysisRevision})</span>
            </>
          ) : (
            <span>Waiting for the engine analysis…</span>
          )}
          {freshness ? <EngStatusChip status={freshness} /> : null}
        </div>
      </header>
      <p className="max-w-3xl text-sm text-muted">
        Science objective → required measurement → instrument capability → engineering consequence → expected return.
        Select an objective to light up the instruments that serve it.
      </p>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <ol className="space-y-4">
          {mission.scienceObjectives.map((o) => {
            const coverage = analysis?.science.weightedObjectiveCoverage[o.id];
            const active = activeId === o.id;
            return (
              <li key={o.id} data-testid={`lab-objective-${o.id}`} className={`panel space-y-3 p-4 ${active ? "is-active" : ""}`}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h3 className="font-semibold">{o.title}</h3>
                    <p className="text-sm text-muted">{o.question}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusPill tone="info">Priority {o.priority}</StatusPill>
                    <span className="font-mono text-xs" data-testid={`lab-coverage-${o.id}`}>
                      {coverage === undefined ? "coverage —" : `coverage ${formatFraction(coverage)}`}
                    </span>
                  </div>
                </div>
                <ul className="space-y-2">
                  {o.requiredMeasurements.map((m: Measurement) => {
                    const { installed, candidates } = providers(m.instrumentCapability, mission, index);
                    const st = !analysis ? null : !current ? "STALE" : missing.has(m.id) ? (m.required ? "FAIL" : "WATCH") : "PASS";
                    return (
                      <li key={m.id} data-testid={`lab-measurement-${m.id}`} className="rounded-lg border border-border bg-background/40 p-3 text-sm">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="min-w-0 font-medium">{m.description}</span>
                          <span className="flex items-center gap-1.5">
                            {m.required ? <StatusPill tone="warn">Required</StatusPill> : <StatusPill>Optional</StatusPill>}
                            {st ? <EngStatusChip status={st} /> : null}
                          </span>
                        </div>
                        <p className="mt-1 flex flex-wrap items-center gap-1 text-xs text-muted">
                          <Telescope aria-hidden className="h-3.5 w-3.5" /> Needs capability{" "}
                          <span className="font-mono text-foreground">{humanize(m.instrumentCapability)}</span>
                          {m.targetThreshold ? <> · target {formatQuantity(m.targetThreshold)}</> : null}
                          <> · weight {m.coverageWeight}</>
                        </p>
                        <div className="mt-2 space-y-1">
                          {installed.map((c) => (
                            <p key={c.id} className="flex flex-wrap items-center gap-2">
                              <ArrowRight aria-hidden className="h-3.5 w-3.5 text-accent-green" />
                              <span className="text-accent-green">{short(c.name)}</span>
                              <span className="text-xs text-muted">installed</span>
                              <Consequence c={c} />
                            </p>
                          ))}
                          {installed.length === 0 ? (
                            <p className="text-xs text-accent-amber">No installed instrument has this capability.</p>
                          ) : null}
                          {candidates.map((c) => (
                            <p key={c.id} className="flex flex-wrap items-center gap-2">
                              <span className="text-muted">Candidate: {short(c.name)}</span>
                              <Consequence c={c} />
                              <button
                                type="button"
                                data-testid={`lab-install-${m.id}-${c.id}`}
                                onClick={(e) => install(c, e.currentTarget)}
                                className="min-h-8 rounded-md border border-accent-cyan/50 px-2 text-xs text-accent-cyan hover:bg-accent-cyan/10"
                              >
                                Install
                              </button>
                            </p>
                          ))}
                        </div>
                      </li>
                    );
                  })}
                </ul>
                <button
                  type="button"
                  aria-pressed={active}
                  data-testid={`lab-focus-${o.id}`}
                  onClick={() => focus(o)}
                  className="min-h-9 rounded-md border border-accent-violet/50 px-3 text-xs font-medium text-accent-violet hover:bg-accent-violet/10"
                >
                  {active ? "Clear highlight" : "Show serving instruments on the spacecraft"}
                </button>
              </li>
            );
          })}
        </ol>
        <div className="space-y-2 lg:sticky lg:top-20 lg:self-start">
          <SpacecraftStage mission={mission} index={index} height="h-80" compact />
          <p className="text-xs text-muted">
            Instrument mass, power and data rate are catalogue gameplay estimates; coverage and return are the engine&apos;s
            analysis of this design revision.
          </p>
        </div>
      </div>
    </div>
  );
}

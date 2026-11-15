"use client";

import { AnimatePresence, motion } from "motion/react";
import { Crosshair, Link2, MapPin, Replace, Trash2, Wrench } from "lucide-react";

import { FidelityBadge } from "@/components/common/FidelityBadge";
import { StatusPill } from "@/components/common/StatusPill";
import { constraintsFor, constraintStatus } from "@/lib/spacecraft/engineering-status";
import { installationLabel, OFF_SPACECRAFT, partsForArchitecture } from "@/lib/spacecraft/part-registry";
import { formatQuantity, humanize } from "@/lib/format";
import { useArchitectUi } from "@/state/architect-ui-store";
import { useMissionStore, type MissionState } from "@/state/mission-store";
import { useState } from "react";
import {
  CATEGORY_ORDER,
  conflictsForCandidate,
  KEY_PARAMETERS,
  selectedIds,
  type CatalogComponent,
} from "./catalog-helpers";
import { requestChange } from "./component-actions";
import { EngStatusChip } from "./EngStatusChip";

const BTN =
  "inline-flex min-h-9 items-center gap-1.5 rounded-md border px-3 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-50";

/** Which component the inspector shows: the selected one, else the active category's choice. */
function inspected(mission: MissionState, index: Map<string, CatalogComponent>, selectedId: string | null, category: CatalogComponent["category"]) {
  if (selectedId && index.has(selectedId)) return index.get(selectedId)!;
  const first = selectedIds(mission, category)[0];
  return first ? index.get(first) : undefined;
}

/**
 * Component inspector (front_design.md 5.1 right panel): the inspected part's catalogue
 * specifications with their provenance, where it is mounted, what it connects to, and the
 * backend constraints that concern its subsystem. Actions edit the canonical MissionState.
 */
export function ComponentInspector({ mission, index }: { mission: MissionState; index: Map<string, CatalogComponent> }) {
  const selectedId = useArchitectUi((s) => s.selectedId);
  const category = useArchitectUi((s) => s.category);
  const ui = useArchitectUi.getState;
  const analysis = useMissionStore((s) => s.analysis);
  const analysisRevision = useMissionStore((s) => s.analysisRevision);
  const status = useMissionStore((s) => s.status);

  const [view, setView] = useState<"quick" | "engineering">("quick");
  const c = inspected(mission, index, selectedId, category);
  if (!c) {
    return (
      <section data-testid="component-inspector" className="panel p-4 text-sm text-muted">
        Select a part in the viewport or the catalogue to inspect it.
      </section>
    );
  }
  const meta = CATEGORY_ORDER.find((m) => m.category === c.category)!;
  const chosen = selectedIds(mission, c.category);
  const installed = chosen.includes(c.id);
  const slot = c.category === "instrument" ? Math.max(0, chosen.indexOf(c.id)) : 0;
  const conflicts = installed ? [] : conflictsForCandidate(index, mission, c.category, c.id);
  const keys = KEY_PARAMETERS[c.category];
  const params = Object.entries(c.parameters).sort(([a], [b]) => {
    const ia = keys.indexOf(a);
    const ib = keys.indexOf(b);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });
  const known = new Set<string>(CATEGORY_ORDER.map((m) => m.category));
  const ruleCategories = [...new Set((c.compatibleWith ?? []).map((r) => r.category))].filter(
    (cat): cat is CatalogComponent["category"] => known.has(cat),
  );
  const connected = ruleCategories.flatMap((cat) => selectedIds(mission, cat).map((id) => index.get(id))).filter((x): x is CatalogComponent => !!x);
  const stale = status === "calculating" || (analysis !== null && analysisRevision !== mission.designRevision);
  const related = analysis ? constraintsFor(analysis.constraints, c.category) : [];

  const install = (e: React.MouseEvent<HTMLButtonElement>) => requestChange(index, c.category, c.id, e.currentTarget);
  const remove = install;
  const current = !installed && !meta.multi ? index.get(chosen[0]) : undefined;

  return (
    <section aria-labelledby="inspector-heading" data-testid="component-inspector" className="panel overflow-hidden">
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={c.id}
          initial={{ opacity: 0, x: 12 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -12 }}
          transition={{ duration: 0.18 }}
          className="space-y-4 p-4"
        >
          <header className="space-y-2">
            <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-primary">Inspector · {meta.label}</p>
            <h2 id="inspector-heading" data-testid="inspector-name" className="text-lg font-semibold leading-tight">
              {c.name}
            </h2>
            <div className="flex flex-wrap gap-1.5">
              {installed ? <StatusPill tone="ok">Installed</StatusPill> : <StatusPill>Not installed</StatusPill>}
              <FidelityBadge fidelity={c.provenance.fidelity} />
              {c.isIllustrative ? <StatusPill tone="warn">Illustrative archetype</StatusPill> : null}
            </div>
            <p className="text-sm text-muted">{c.description}</p>
          </header>

          <div className="space-y-1 text-sm">
            <p className="flex items-center gap-1.5 text-muted">
              <MapPin aria-hidden className="h-3.5 w-3.5" />
              {OFF_SPACECRAFT.has(c.category)
                ? installationLabel(c.category)
                : (partsForArchitecture(mission.architecture, index).find((p) => p.componentId === c.id)?.mountLabel ??
                  installationLabel(c.category, slot))}
            </p>
            <p className="text-[11px] text-muted">3D shape: procedural placeholder (no verified model or dimensions).</p>
          </div>

          <div>
            <div className="mb-1 flex items-center justify-between gap-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Specifications (catalogue)</h3>
              <div role="group" aria-label="Detail level" className="flex gap-1 text-xs">
                {(["quick", "engineering"] as const).map((v) => (
                  <button
                    key={v}
                    type="button"
                    aria-pressed={view === v}
                    data-testid={`inspector-view-${v}`}
                    onClick={() => setView(v)}
                    className={`rounded border px-2 py-0.5 ${view === v ? "border-accent-cyan/60 text-accent-cyan" : "border-border text-muted"}`}
                  >
                    {v === "quick" ? "Quick view" : "Engineering view"}
                  </button>
                ))}
              </div>
            </div>
            <dl data-testid="inspector-specs" className="divide-y divide-border/60 rounded-lg border border-border text-sm">
              {current ? (
                <div className="flex items-center justify-between gap-3 px-3 py-1 text-[11px] text-muted">
                  <span>Specification</span>
                  <span>This · installed ({current.name.replace(/^Archetype:\s*/, "")})</span>
                </div>
              ) : null}
              {(view === "quick" ? params.filter(([k]) => keys.includes(k)) : params).map(([key, q]) => (
                <div key={key} className="flex items-center justify-between gap-3 px-3 py-1.5">
                  <dt className="text-muted">{humanize(key)}</dt>
                  <dd className="readout text-right" title={q.provenance.assumptions?.join(" ")}>
                    {formatQuantity(q)}
                    {current ? <span className="text-muted"> · {current.parameters[key] ? formatQuantity(current.parameters[key]) : "—"}</span> : null}
                  </dd>
                </div>
              ))}
            </dl>
            {(c.capabilities ?? []).length > 0 ? (
              <p className="mt-2 text-xs text-muted">Capabilities: {(c.capabilities ?? []).map(humanize).join(", ")}</p>
            ) : null}
            {view === "engineering" ? (
              <div className="mt-2 space-y-1 text-xs text-muted">
                <p>
                  Source: {c.provenance.sourceName}
                  {c.provenance.sourceVersion ? ` v${c.provenance.sourceVersion}` : ""} · fidelity {c.provenance.fidelity} · record {c.sourceRecordId}
                </p>
                {(c.provenance.assumptions ?? []).map((a) => (
                  <p key={a}>Assumption: {a}</p>
                ))}
                {(c.failureModes ?? []).length > 0 ? (
                  <div>
                    <p className="font-medium text-foreground">Failure modes (gameplay estimates)</p>
                    <ul className="list-disc pl-4">
                      {(c.failureModes ?? []).map((fm) => (
                        <li key={fm.id}>{fm.description}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>

          {connected.length > 0 ? (
            <div>
              <h3 className="mb-1 flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-muted">
                <Link2 aria-hidden className="h-3.5 w-3.5" /> Connected components
              </h3>
              <ul className="space-y-1 text-sm">
                {connected.map((o) => (
                  <li key={o.id}>
                    <button type="button" className="text-left text-accent-cyan underline-offset-2 hover:underline" onClick={() => ui().select(o.id, o.category)}>
                      {o.name}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted">Constraints on this subsystem</h3>
            {!analysis ? (
              <p className="text-xs text-muted">Waiting for the first analysis.</p>
            ) : related.length === 0 ? (
              <p className="text-xs text-muted">No engine constraint is linked to this subsystem.</p>
            ) : (
              <ul data-testid="inspector-constraints" className="space-y-1.5">
                {related.map((k) => (
                  <li key={k.id} className="flex items-start justify-between gap-2 text-sm">
                    <span className="min-w-0">
                      <span className="block truncate">{k.label}</span>
                      {k.status !== "pass" ? <span className="block text-xs text-muted">{k.explanation}</span> : null}
                    </span>
                    <EngStatusChip status={stale ? "STALE" : constraintStatus(k)} />
                  </li>
                ))}
              </ul>
            )}
          </div>

          {conflicts.length > 0 ? (
            <p role="note" className="rounded-md border border-accent-amber/50 bg-accent-amber/10 p-2 text-xs text-accent-amber">
              Incompatible: {conflicts[0].message} Choosing it asks you to confirm first.
            </p>
          ) : null}

          <div className="flex flex-wrap gap-2">
            {!installed ? (
              <button type="button" data-testid="inspector-install" className={`${BTN} border-accent-cyan/60 bg-accent-cyan/10 text-accent-cyan hover:bg-accent-cyan/20`} onClick={install}>
                <Wrench aria-hidden className="h-3.5 w-3.5" /> {meta.multi ? "Add to spacecraft" : "Replace installed…"}
              </button>
            ) : null}
            {installed && meta.multi ? (
              <button type="button" data-testid="inspector-remove" className={`${BTN} border-accent-red/50 text-accent-red hover:bg-accent-red/10`} onClick={remove}>
                <Trash2 aria-hidden className="h-3.5 w-3.5" /> Remove
              </button>
            ) : null}
            <button type="button" data-testid="inspector-replace" className={`${BTN} border-border text-muted hover:text-foreground`} onClick={() => ui().setCategory(c.category)}>
              <Replace aria-hidden className="h-3.5 w-3.5" /> {meta.multi ? "Browse instruments" : "Replace…"}
            </button>
            {installed && !OFF_SPACECRAFT.has(c.category) ? (
              <button type="button" className={`${BTN} border-border text-muted hover:text-foreground`} onClick={() => ui().focusSelected()}>
                <Crosshair aria-hidden className="h-3.5 w-3.5" /> Focus in 3D
              </button>
            ) : null}
          </div>
        </motion.div>
      </AnimatePresence>
    </section>
  );
}

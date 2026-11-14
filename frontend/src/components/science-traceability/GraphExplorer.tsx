"use client";

import { ArrowDown, ArrowUp, Crosshair, Network } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { ConstraintBadge } from "@/components/common/ConstraintBadge";
import { FidelityBadge } from "@/components/common/FidelityBadge";
import { StatusPill } from "@/components/common/StatusPill";
import { ACTION_CLASS } from "@/components/common/States";
import { formatFraction, formatNumber } from "@/lib/format";
import { useMissionStore } from "@/state/mission-store";
import {
  COLUMNS,
  KIND_LABEL,
  METRIC_LABEL,
  STATUS_TEXT,
  labelFromKey,
  nodeConstraints,
  plainAttributes,
  relations,
  worstStatus,
  type ArchitectureGraph,
  type ArchitectureNode,
  type Relation,
} from "./graph-model";
import { useArchitectureGraph, type ImpactView } from "./useArchitectureGraph";

/** Contacts beyond this are folded behind "Show all" unless related to the selection. */
const CONTACTS_SHOWN = 3;

const RELATION_STYLE: Record<Relation, string> = {
  selected: "border-accent-cyan bg-accent-cyan/10",
  affects: "border-accent-amber/70",
  "depends-on": "border-accent-cyan/50",
  unrelated: "border-border opacity-40",
};

function RelationTag({ relation }: { relation: Relation | undefined }) {
  if (relation === "selected")
    return (
      <span className="inline-flex items-center gap-1 text-xs text-accent-cyan">
        <Crosshair aria-hidden className="h-3 w-3" /> Selected
      </span>
    );
  if (relation === "affects")
    return (
      <span className="inline-flex items-center gap-1 text-xs text-accent-amber">
        <ArrowDown aria-hidden className="h-3 w-3" /> Affected by selection
      </span>
    );
  if (relation === "depends-on")
    return (
      <span className="inline-flex items-center gap-1 text-xs text-accent-cyan">
        <ArrowUp aria-hidden className="h-3 w-3" /> Selection depends on this
      </span>
    );
  return null;
}

function formatAttr(key: string, value: string | number | boolean): string {
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "string") return STATUS_TEXT[value] ?? value;
  if (/Fraction$/.test(key) || key === "coverage") return formatFraction(value);
  return formatNumber(value);
}

function NodeButton({
  node,
  relation,
  onSelect,
}: {
  node: ArchitectureNode;
  relation: Relation | undefined;
  onSelect: (id: string) => void;
}) {
  const status = node.attributes?.status;
  const worst = worstStatus(node);
  return (
    <li>
      <button
        type="button"
        data-testid={`graph-node-${node.id}`}
        data-relation={relation ?? "none"}
        aria-pressed={relation === "selected"}
        onClick={() => onSelect(node.id)}
        className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition-opacity hover:bg-white/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent-cyan ${
          relation ? RELATION_STYLE[relation] : "border-border"
        }`}
      >
        <span className="block break-words">{node.label}</span>
        <span className="mt-1 flex flex-wrap items-center gap-2">
          {typeof status === "string" ? (
            <span
              className={`text-xs font-medium ${status === "uncovered" ? "text-red-300" : status === "covered" ? "text-accent-cyan" : "text-accent-amber"}`}
            >
              {STATUS_TEXT[status] ?? status}
            </span>
          ) : null}
          {worst && worst !== "pass" && worst !== "not-modelled" ? <ConstraintBadge status={worst} /> : null}
          <RelationTag relation={relation} />
        </span>
      </button>
    </li>
  );
}

function NodeDetail({ graph, node }: { graph: ArchitectureGraph; node: ArchitectureNode }) {
  const analysis = useMissionStore((s) => s.analysis);
  const constraintsById = useMemo(() => new Map(analysis?.constraints.map((c) => [c.id, c]) ?? []), [analysis]);
  const byId = new Map(graph.nodes.map((n) => [n.id, n]));
  const incoming = graph.edges.filter((e) => e.toId === node.id);
  const outgoing = graph.edges.filter((e) => e.fromId === node.id);
  const attrs = plainAttributes(node);
  const verdicts = nodeConstraints(node);

  return (
    <div data-testid="graph-detail" className="space-y-4 rounded-xl border border-border bg-surface p-4">
      <div>
        <p className="text-xs uppercase tracking-wide text-muted">{KIND_LABEL[node.kind]}</p>
        <h3 className="mt-1 break-words font-semibold">{node.label}</h3>
      </div>
      {verdicts.length > 0 ? (
        <div className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">Constraints checked here</h4>
          <ul className="space-y-2">
            {verdicts.map((v) => (
              <li key={v.id} data-testid={`graph-constraint-${v.id}`} className="text-sm">
                <span className="flex flex-wrap items-center gap-2">
                  <ConstraintBadge status={v.status} />
                  {constraintsById.get(v.id)?.label ?? v.id}
                </span>
                {constraintsById.get(v.id) && v.status !== "pass" ? (
                  <p className="mt-1 text-xs text-muted">{constraintsById.get(v.id)?.explanation}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {attrs.length > 0 ? (
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          {attrs.map(([key, value]) => (
            <div key={key} className="contents">
              <dt className="text-muted">{labelFromKey(key)}</dt>
              <dd className="break-words font-mono text-xs leading-5">{formatAttr(key, value)}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      <EdgeList
        title="Depends on"
        icon={<ArrowUp aria-hidden className="h-3.5 w-3.5" />}
        items={incoming.map((e) => ({ id: e.id, other: byId.get(e.fromId)?.label ?? e.fromId, kind: e.kind, why: e.rationale }))}
        empty="Nothing upstream: this is where the chain starts."
      />
      <EdgeList
        title="Affects"
        icon={<ArrowDown aria-hidden className="h-3.5 w-3.5" />}
        items={outgoing.map((e) => ({ id: e.id, other: byId.get(e.toId)?.label ?? e.toId, kind: e.kind, why: e.rationale }))}
        empty="Nothing downstream in this model."
      />
    </div>
  );
}

function EdgeList({
  title,
  icon,
  items,
  empty,
}: {
  title: string;
  icon: ReactNode;
  items: { id: string; other: string; kind: string; why: string }[];
  empty: string;
}) {
  return (
    <div className="space-y-2">
      <h4 className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-muted">
        {icon}
        {title} ({items.length})
      </h4>
      {items.length === 0 ? (
        <p className="text-sm text-muted">{empty}</p>
      ) : (
        <ul className="max-h-64 space-y-2 overflow-y-auto pr-1 text-sm">
          {items.map((i) => (
            <li key={i.id}>
              <span className="font-medium">{i.other}</span>{" "}
              <span className="font-mono text-xs text-muted">({i.kind})</span>
              <p className="text-xs text-muted">{i.why}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function WhyChanged({ impact, objectiveTitle }: { impact: ImpactView | null; objectiveTitle: (id: string) => string }) {
  const analysis = useMissionStore((s) => s.analysis);
  const label = (id: string) => analysis?.constraints.find((c) => c.id === id)?.label ?? id;
  if (!impact) {
    return (
      <p data-testid="graph-why-empty" className="text-sm text-muted">
        Make a design change (for example swap the radio) and this list explains what it affected.
      </p>
    );
  }
  const r = impact.report;
  const nothing =
    r.changedMetrics.length === 0 && r.newlyViolated.length === 0 && r.improved.length === 0 && r.affectedObjectives.length === 0;
  return (
    <div data-testid="graph-why-changed" className="space-y-3 text-sm">
      <p className="text-xs text-muted">
        Revision {impact.beforeRevision} to revision {impact.afterRevision}
      </p>
      {nothing ? <p>This edit did not change any modelled metric, constraint or objective.</p> : null}
      {r.newlyViolated.length > 0 ? (
        <div>
          <h4 className="font-semibold text-red-300">Got worse</h4>
          <ul className="list-disc pl-5" data-testid="graph-why-worse">
            {r.newlyViolated.map((id) => (
              <li key={id}>{label(id)}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {r.improved.length > 0 ? (
        <div>
          <h4 className="font-semibold text-accent-cyan">Improved</h4>
          <ul className="list-disc pl-5" data-testid="graph-why-improved">
            {r.improved.map((id) => (
              <li key={id}>{label(id)}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {r.affectedObjectives.length > 0 ? (
        <div>
          <h4 className="font-semibold">Science objectives affected</h4>
          <ul className="list-disc pl-5" data-testid="graph-why-objectives">
            {r.affectedObjectives.map((id) => (
              <li key={id}>{objectiveTitle(id)}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {r.changedMetrics.length > 0 ? (
        <div>
          <h4 className="font-semibold">Numbers that moved</h4>
          <ul className="space-y-0.5" data-testid="graph-why-metrics">
            {r.changedMetrics.map((m) => {
              const fraction = m.unit === "fraction";
              const show = (v: number) => (fraction ? formatFraction(v) : `${formatNumber(v)} ${m.unit}`);
              return (
                <li key={m.metric}>
                  {METRIC_LABEL[m.metric] ?? labelFromKey(m.metric)}: {show(m.before)} to {show(m.after)}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

/**
 * Architecture graph explorer (Task 6.1). Columns, not a free layout: objectives ->
 * measurements -> instruments -> spacecraft -> operations. Selecting a node highlights
 * what it affects (downstream) and what it depends on (upstream), each labelled in text.
 * The graph and every number come from the Python backend.
 */
export function GraphExplorer() {
  const { data, status, impact, retry } = useArchitectureGraph();
  const currentRevision = useMissionStore((s) => s.designRevision);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showAllContacts, setShowAllContacts] = useState(false);

  const graph = data?.graph ?? null;
  const selected = graph?.nodes.find((n) => n.id === selectedId) ?? null;
  const rel = useMemo(() => (graph ? relations(graph, selected ? selected.id : null) : new Map()), [graph, selected]);
  const objectiveTitle = (id: string) => graph?.nodes.find((n) => n.id === `objective:${id}`)?.label ?? id;
  const stale = data !== null && data.designRevision !== currentRevision;

  return (
    <section
      aria-labelledby="graph-explorer-title"
      data-testid="graph-explorer"
      className="space-y-4 rounded-xl border border-border bg-surface/40 p-4"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h2 id="graph-explorer-title" className="flex items-center gap-2 text-lg font-semibold">
            <Network aria-hidden className="h-5 w-5 text-accent-cyan" />
            Architecture graph
          </h2>
          <p className="max-w-3xl text-sm text-muted">
            How your science goals, instruments, spacecraft subsystems and operations depend on each other. Select
            any box to see what it affects and what it depends on.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {data ? (
            <StatusPill testId="graph-revision" tone={stale ? "warn" : "info"}>
              {stale ? `Showing revision ${data.designRevision} (updating)` : `Revision ${data.designRevision}`}
            </StatusPill>
          ) : null}
          <FidelityBadge fidelity="derived" />
        </div>
      </header>

      {status === "error" ? (
        <div role="alert" className="flex flex-wrap items-center gap-3 text-sm text-accent-amber">
          Graph could not be built for this revision{data ? "; showing the last good graph" : ""}.
          <button type="button" className={ACTION_CLASS} onClick={retry}>
            Retry
          </button>
        </div>
      ) : null}

      {!graph ? (
        status === "error" ? null : (
          <p role="status" className="text-sm text-muted">
            Building the architecture graph...
          </p>
        )
      ) : (
        <div className="grid gap-4 xl:grid-cols-[1fr_22rem]">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {COLUMNS.map((col) => {
              const nodes = graph.nodes.filter((n) => col.kinds.includes(n.kind));
              const contacts = nodes.filter((n) => n.kind === "contact-window");
              const hidden =
                showAllContacts || contacts.length <= CONTACTS_SHOWN
                  ? new Set<string>()
                  : new Set(
                      contacts
                        .slice(CONTACTS_SHOWN)
                        .filter((n) => !["selected", "affects", "depends-on"].includes(rel.get(n.id) ?? ""))
                        .map((n) => n.id),
                    );
              return (
                <div key={col.id} data-testid={`graph-column-${col.id}`} className="min-w-0 space-y-2">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">
                    {col.title} ({nodes.length})
                  </h3>
                  {nodes.length === 0 ? (
                    <p className="text-sm text-muted">None in this design.</p>
                  ) : (
                    <ul className="space-y-2">
                      {nodes
                        .filter((n) => !hidden.has(n.id))
                        .map((n) => (
                          <NodeButton
                            key={n.id}
                            node={n}
                            relation={rel.get(n.id)}
                            onSelect={(id) => setSelectedId((cur) => (cur === id ? null : id))}
                          />
                        ))}
                    </ul>
                  )}
                  {hidden.size > 0 ? (
                    <button
                      type="button"
                      onClick={() => setShowAllContacts(true)}
                      className="text-xs text-accent-cyan underline-offset-2 hover:underline"
                    >
                      Show all {contacts.length} contacts ({hidden.size} hidden)
                    </button>
                  ) : null}
                </div>
              );
            })}
          </div>
          <div className="space-y-4">
            {selected ? (
              <NodeDetail graph={graph} node={selected} />
            ) : (
              <p className="rounded-xl border border-dashed border-border p-4 text-sm text-muted">
                Select a box to see its numbers, the constraints checked on it, and why each link exists.
              </p>
            )}
            <div className="space-y-2 rounded-xl border border-border bg-surface p-4">
              <h3 className="font-semibold">Why did this change?</h3>
              <WhyChanged impact={impact} objectiveTitle={objectiveTitle} />
            </div>
          </div>
        </div>
      )}
      <p className="text-xs text-muted">
        Links are the game&apos;s engineering model (derived), not flight heritage. Constraint verdicts are shown on the
        part of the spacecraft they check.
      </p>
    </section>
  );
}

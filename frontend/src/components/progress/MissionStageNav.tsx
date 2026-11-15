"use client";

import { CircleAlert, CircleCheck, CircleDot, Circle } from "lucide-react";
import Link from "next/link";

import type { Stage, StageStatus } from "@/lib/progress/progress";

export type StageView = "brief" | "science" | "architect" | "arena" | "readiness" | "control" | "review";

const ORDER: { view: StageView; label: string; stages: string[] }[] = [
  { view: "brief", label: "Brief", stages: ["accept"] },
  { view: "science", label: "Science lab", stages: ["science"] },
  { view: "architect", label: "Architect", stages: ["build"] },
  { view: "arena", label: "Trade study", stages: ["trade"] },
  { view: "readiness", label: "Readiness", stages: ["gates", "readiness"] },
  { view: "control", label: "Mission control", stages: ["fly"] },
  { view: "review", label: "Review", stages: ["review"] },
];

const RANK: Record<StageStatus, number> = { attention: 0, current: 1, todo: 2, complete: 3 };
const ICON = { complete: CircleCheck, current: CircleDot, attention: CircleAlert, todo: Circle } as const;
const WORD: Record<StageStatus, string> = { complete: "complete", current: "current step", attention: "needs attention", todo: "not started" };

/**
 * Mission stage rail (design_update.md 5.1): every destination with its real status
 * (complete / current / needs attention / not started). Never locks a stage: Mission control
 * and Review open the latest flown run; before any run they open the launch panel and say so.
 */
export function MissionStageNav({
  missionId,
  view,
  stages,
  latestRunId,
}: {
  missionId: string;
  view: StageView;
  stages: Stage[];
  latestRunId: string | null;
}) {
  const href = (v: StageView) =>
    v === "brief"
      ? `/mission/${missionId}`
      : v === "science"
        ? `/science/${missionId}`
        : v === "architect"
          ? `/architect/${missionId}`
          : v === "arena"
            ? `/arena/${missionId}`
            : v === "readiness"
              ? `/readiness/${missionId}`
              : latestRunId
              ? `/${v === "control" ? "control" : "review"}/${latestRunId}`
              : null;

  return (
    <nav aria-label="Mission workspace" data-testid="stage-nav" className="flex flex-wrap gap-1.5">
      {ORDER.map(({ view: v, label, stages: ids }, i) => {
        const own = stages.filter((s) => ids.includes(s.id));
        const status: StageStatus = own.length ? [...own].sort((a, b) => RANK[a.status] - RANK[b.status])[0].status : "todo";
        const Icon = ICON[status];
        const active = v === view;
        const target = href(v);
        const tone =
          status === "complete" ? "text-accent-green" : status === "attention" ? "text-accent-amber" : status === "current" ? "text-accent-cyan" : "text-muted";
        const cls = `inline-flex min-h-11 items-center gap-2 rounded-lg border px-3 text-sm font-medium ${
          active ? "is-active panel border-accent-cyan/60 text-foreground" : "border-border bg-surface/60 text-muted hover:border-accent-cyan/40 hover:text-foreground"
        }`;
        const body = (
          <>
            <span aria-hidden className="font-mono text-[10px] text-muted">{i + 1}</span>
            <Icon aria-hidden className={`h-4 w-4 ${tone}`} />
            {label}
          </>
        );
        // Before any flight there is no run to show: the link opens the launch panel instead,
        // so the stage is never a dead end.
        const flown = target !== null;
        const to = target ?? `/architect/${missionId}#launch`;
        return (
          <Link
            key={v}
            href={to}
            aria-label={label}
            aria-describedby={`stage-status-${v}`}
            aria-current={active ? "page" : undefined}
            data-stage-status={status}
            data-testid={`stage-link-${v}`}
            title={flown ? undefined : "Not flown yet: opens the launch panel in the architect"}
            className={cls}
          >
            {body}
            {flown ? null : <span className="text-[10px] font-normal text-muted">· launch first</span>}
            <span id={`stage-status-${v}`} className="sr-only">
              {flown ? WORD[status] : "not flown yet; opens the launch panel"}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}

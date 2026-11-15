"use client";

import { Award, ChevronDown, CircleAlert, CircleCheck, CircleDot, Circle, Star, Target, Trophy } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef } from "react";

import { BADGES, type Stage } from "@/lib/progress/progress";
import { milestone } from "@/lib/motion/motion";
import type { useMissionProgress } from "./useMissionProgress";

type Progress = NonNullable<ReturnType<typeof useMissionProgress>>;

const ICON = { complete: CircleCheck, current: CircleDot, attention: CircleAlert, todo: Circle } as const;
const TONE = { complete: "text-accent-green", current: "text-accent-cyan", attention: "text-accent-amber", todo: "text-muted" } as const;

/** Earned-badge acknowledgement: only for a genuinely new badge, dismissible, announced politely. */
function BadgeToast({ ids, onClose }: { ids: string[]; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    milestone(ref.current);
  }, [ids]);
  if (ids.length === 0) return null;
  const badges = BADGES.filter((b) => ids.includes(b.id));
  return (
    <div ref={ref} role="status" data-testid="badge-toast" className="panel is-active flex items-start gap-3 p-3">
      <Trophy aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-accent-amber" />
      <div className="min-w-0 flex-1 text-sm">
        {badges.map((b) => (
          <p key={b.id}>
            <span className="font-semibold">Milestone: {b.title}.</span> <span className="text-muted">{b.why}</span>
          </p>
        ))}
      </div>
      <button type="button" onClick={onClose} className="btn btn-tertiary min-h-8 px-2 text-xs">
        Dismiss
      </button>
    </div>
  );
}

function StageRow({ s }: { s: Stage }) {
  const Icon = ICON[s.status];
  return (
    <li data-testid={`milestone-${s.id}`} data-status={s.status} className="flex items-start gap-2 text-sm">
      <Icon aria-hidden className={`mt-0.5 h-4 w-4 shrink-0 ${TONE[s.status]}`} />
      <div className="min-w-0">
        <p className="font-medium">
          {s.title} <span className="sr-only">({s.status})</span>
        </p>
        <p className="text-xs text-muted">{s.status === "complete" ? s.detail : `${s.objective} ${s.detail}`}</p>
      </div>
    </li>
  );
}

/**
 * Mission progress (design_update.md 7.1 / 7.3): the recommended next action, milestone
 * progress, earned badges and optional challenges. Free exploration stays possible; this only
 * makes the next useful step obvious.
 */
export function MissionProgress({ progress }: { progress: Progress }) {
  const done = progress.stages.filter((s) => s.status === "complete").length;
  const next = progress.next;
  return (
    <div className="space-y-2">
      <BadgeToast ids={progress.fresh} onClose={progress.clearFresh} />
      <div data-testid="mission-progress" className="panel flex flex-wrap items-center gap-x-4 gap-y-2 p-3">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <Target aria-hidden className="h-5 w-5 shrink-0 text-accent-cyan" />
          <div className="min-w-0">
            <p className="text-[11px] uppercase tracking-[0.2em] text-muted">Recommended next step</p>
            {next ? (
              <p className="text-sm" data-testid="next-action">
                <span className="font-semibold">{next.title}.</span> <span className="text-muted">{next.detail}</span>
              </p>
            ) : (
              <p className="text-sm font-semibold text-accent-green" data-testid="next-action">
                All milestones complete. Try a challenge or fly a variant.
              </p>
            )}
          </div>
        </div>
        {next ? (
          <Link href={next.href} className="btn btn-primary" data-testid="next-action-go">
            Go
          </Link>
        ) : null}
        <div className="flex items-center gap-2" aria-label={`${done} of ${progress.stages.length} milestones complete`}>
          <div aria-hidden className="h-1.5 w-28 overflow-hidden rounded-full bg-border">
            <div className="h-full rounded-full bg-accent-green transition-[width] duration-500" style={{ width: `${(done / progress.stages.length) * 100}%` }} />
          </div>
          <span className="readout text-xs text-muted" data-testid="milestone-count">
            {done}/{progress.stages.length}
          </span>
        </div>
        <details className="group w-full">
          <summary className="flex min-h-9 cursor-pointer list-none items-center gap-1.5 text-xs font-medium text-muted hover:text-foreground">
            <ChevronDown aria-hidden className="h-3.5 w-3.5 transition-transform group-open:rotate-180" />
            Milestones, badges and challenges
          </summary>
          <div className="mt-2 grid gap-4 md:grid-cols-3">
            <ol className="space-y-2">
              {progress.stages.map((s) => (
                <StageRow key={s.id} s={s} />
              ))}
            </ol>
            <div>
              <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted">
                <Award aria-hidden className="h-3.5 w-3.5" /> Badges
              </p>
              <ul className="space-y-1.5" data-testid="badges">
                {BADGES.map((b) => {
                  const earned = progress.badges.includes(b.id);
                  return (
                    <li key={b.id} data-earned={earned} className={`text-sm ${earned ? "" : "text-muted"}`}>
                      <span className={earned ? "font-medium text-accent-amber" : ""}>
                        <Star aria-hidden className={`mr-1 inline h-3.5 w-3.5 ${earned ? "fill-accent-amber" : ""}`} />
                        {b.title}
                      </span>
                      <span className="sr-only">{earned ? " (earned)" : " (not yet)"}</span>
                      <span className="block text-xs text-muted">{b.why}</span>
                    </li>
                  );
                })}
              </ul>
            </div>
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted">Optional challenges</p>
              <ul className="space-y-1.5" data-testid="challenges">
                {progress.challenges.map((c) => (
                  <li key={c.id} data-met={String(c.met)} className="text-sm">
                    <span className="font-medium">{c.title}</span>{" "}
                    <span className={c.met ? "text-accent-green" : c.met === false ? "text-muted" : "text-muted"}>
                      {c.met === null ? "(needs a current analysis)" : c.met ? "· met" : "· not yet"}
                    </span>
                    <span className="block text-xs text-muted">Judged by the engine: {c.basis}.</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </details>
      </div>
    </div>
  );
}

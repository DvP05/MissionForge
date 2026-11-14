"use client";

import { GraduationCap } from "lucide-react";
import { useState } from "react";

import { ACTION_CLASS } from "@/components/common/States";
import { useLocalValue } from "@/lib/learning/useLocalValue";

/** Three questions mapped to LO-3, LO-4 and LO-5 (prod 8.x: optional pre/post check). */
const QUESTIONS = [
  {
    id: "q-energy",
    lo: "LO-3",
    text: "A 100 W instrument runs for 30 minutes. What does that cost the battery?",
    options: [
      { id: "a", label: "100 W of power" },
      { id: "b", label: "50 Wh of energy", correct: true },
      { id: "c", label: "Nothing, if the solar arrays produce more than 100 W on average" },
    ],
  },
  {
    id: "q-c3",
    lo: "LO-4",
    text: "The launch gives a high C3. Does the spacecraft still need its own delta-v to rendezvous with an asteroid?",
    options: [
      { id: "a", label: "No: C3 already covers every manoeuvre" },
      { id: "b", label: "Yes: C3 is launch energy; matching the target's speed is the spacecraft's job", correct: true },
      { id: "c", label: "Only if the launch vehicle is small" },
    ],
  },
  {
    id: "q-return",
    lo: "LO-5",
    text: "The camera collected 40 Gbit but the radio can only send 10 Gbit before storage fills. How much science counts?",
    options: [
      { id: "a", label: "All 40 Gbit: it was collected" },
      { id: "b", label: "At most what reaches Earth, about 10 Gbit", correct: true },
      { id: "c", label: "None, the mission failed" },
    ],
  },
] as const;

type Answers = Record<string, string>;

function score(a: Answers): number {
  return QUESTIONS.filter((q) => q.options.some((o) => "correct" in o && o.id === a[q.id])).length;
}

function parse(raw: string | null): Answers | null {
  if (!raw) return null;
  try {
    const v = JSON.parse(raw) as unknown;
    return v && typeof v === "object" ? (v as Answers) : null;
  } catch {
    return null;
  }
}

/**
 * Optional, non-blocking learning check. ``phase="pre"`` on the landing page,
 * ``phase="post"`` on the review (compares with the pre-check). Stored in this browser only.
 */
export function LearningCheck({ phase }: { phase: "pre" | "post" }) {
  const [raw, setRaw] = useLocalValue(`missionforge:learning-check:${phase}`);
  const [preRaw] = useLocalValue("missionforge:learning-check:pre");
  const saved = parse(raw);
  const pre = parse(preRaw);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Answers>({});
  const title = phase === "pre" ? "Optional 1-minute pre-check" : "Optional post-check";

  return (
    <section data-testid={`learning-check-${phase}`} aria-labelledby={`learning-${phase}-h`} className="space-y-3 rounded-xl border border-border p-4">
      <h2 id={`learning-${phase}-h`} className="flex items-center gap-2 text-base font-semibold">
        <GraduationCap aria-hidden className="h-4 w-4 text-accent-cyan" />
        {title}
      </h2>
      {saved ? (
        <div className="space-y-1 text-sm">
          <p data-testid={`learning-${phase}-score`}>
            You answered {score(saved)} of {QUESTIONS.length} correctly.
            {phase === "post" && pre ? ` Before playing: ${score(pre)} of ${QUESTIONS.length}.` : ""}
          </p>
          <button type="button" className="text-xs text-accent-cyan underline" onClick={() => setRaw(null)}>
            Clear my answers
          </button>
        </div>
      ) : !open ? (
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-sm text-muted">
            {phase === "pre"
              ? "Three quick questions before you play, so you can see what changes afterwards."
              : "The same three questions again, now that you have flown a mission."}
          </p>
          <button type="button" data-testid={`learning-${phase}-start`} className={ACTION_CLASS} onClick={() => setOpen(true)}>
            Start the {phase === "pre" ? "pre" : "post"}-check
          </button>
        </div>
      ) : (
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            setRaw(JSON.stringify(draft));
          }}
        >
          {QUESTIONS.map((q) => (
            <fieldset key={q.id} className="space-y-1">
              <legend className="text-sm font-medium">
                {q.text} <span className="text-xs text-muted">({q.lo})</span>
              </legend>
              {q.options.map((o) => (
                <label key={o.id} className="flex min-h-11 cursor-pointer items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name={`${phase}-${q.id}`}
                    value={o.id}
                    checked={draft[q.id] === o.id}
                    onChange={() => setDraft((d) => ({ ...d, [q.id]: o.id }))}
                    className="h-4 w-4 accent-cyan-400"
                  />
                  {o.label}
                </label>
              ))}
            </fieldset>
          ))}
          <button
            type="submit"
            data-testid={`learning-${phase}-submit`}
            disabled={Object.keys(draft).length < QUESTIONS.length}
            className={`${ACTION_CLASS} disabled:cursor-not-allowed disabled:opacity-50`}
          >
            Save my answers
          </button>
        </form>
      )}
      <p className="text-xs text-muted">
        Stored only in this browser. Nothing is sent anywhere and no analytics are collected. A single session does
        not measure learning.
      </p>
    </section>
  );
}

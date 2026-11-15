"use client";

import { animate } from "animejs";
import { useReducedMotion } from "motion/react";
import { useMotionPref } from "@/components/shell/MotionToggle";
import { useEffect, useRef } from "react";

/**
 * Launch sequence indicator (anime.js), shown only while the simulation request is in flight.
 * It signals real work in progress; it never stands in for a result or hides a failure, and it
 * is static text under reduced motion.
 */
export function LaunchSequence() {
  const bar = useRef<HTMLSpanElement>(null);
  const pref = useMotionPref();
  const reduced = (useReducedMotion() ?? false) || pref === "reduced";

  useEffect(() => {
    if (reduced || !bar.current) return;
    const sweep = animate(bar.current, {
      translateX: ["-100%", "250%"],
      duration: 1100,
      ease: "inOutSine",
      loop: true,
    });
    return () => {
      sweep.pause();
    };
  }, [reduced]);

  return (
    <div role="status" data-testid="launch-sequence" className="flex min-w-48 flex-1 items-center gap-3">
      <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-accent-amber">Ignition · engine running</span>
      <span aria-hidden className="relative h-1 flex-1 overflow-hidden rounded-full bg-border">
        <span ref={bar} className="absolute inset-y-0 left-0 w-1/3 rounded-full bg-gradient-to-r from-transparent via-accent-amber to-transparent" />
      </span>
    </div>
  );
}

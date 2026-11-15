/**
 * MISSIONFORGE motion system (design_update.md section 11). One place for durations, easing
 * and the reusable anime.js helpers, so components never hand-roll timelines.
 *
 * Rules: motion only presents a real state change (a returned analysis, an installed part, a
 * passed gate). It never animates invented intermediate engineering values, never runs
 * before the backend has answered, and every helper is a no-op under reduced motion.
 */
import { animate, type JSAnimation } from "animejs";

export const MOTION = {
  micro: 150,
  panel: 220,
  state: 360,
  milestone: 600,
} as const;

export const EASE = {
  out: "outCubic",
  inOut: "inOutCubic",
  settle: "outBack(1.4)",
} as const;

const MOTION_PREF_KEY = "missionforge:motion";
export type MotionPref = "system" | "reduced";

/** Player override (settings menu) on top of the OS preference. */
export function readMotionPref(): MotionPref {
  try {
    return window.localStorage.getItem(MOTION_PREF_KEY) === "reduced" ? "reduced" : "system";
  } catch {
    return "system";
  }
}

export function writeMotionPref(pref: MotionPref): void {
  try {
    window.localStorage.setItem(MOTION_PREF_KEY, pref);
  } catch {
    /* storage unavailable: the choice lasts for this page view */
  }
  document.documentElement.dataset.motion = pref;
  window.dispatchEvent(new Event("missionforge:motion"));
}

/** True when motion should be skipped (OS setting or the player's override). */
export function motionReduced(): boolean {
  if (typeof window === "undefined") return true;
  if (document.documentElement.dataset.motion === "reduced" || readMotionPref() === "reduced") return true;
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

type Target = HTMLElement | null | undefined;
const run = (el: Target, params: Parameters<typeof animate>[1]): JSAnimation | null =>
  !el || motionReduced() ? null : animate(el, params);

/** A value just replaced by a confirmed backend result: brief lift + accent wash. */
export function emphasiseChange(el: Target): JSAnimation | null {
  return run(el, { translateY: [4, 0], opacity: [0.35, 1], duration: MOTION.state, ease: EASE.out });
}

/** A panel or card entering. */
export function enter(el: Target, delay = 0): JSAnimation | null {
  return run(el, { opacity: [0, 1], translateY: [8, 0], duration: MOTION.panel, delay, ease: EASE.out });
}

/** A gate or badge reaching a new state (scale settle; no looping). */
export function settle(el: Target): JSAnimation | null {
  return run(el, { scale: [0.92, 1], opacity: [0.4, 1], duration: MOTION.state, ease: EASE.settle });
}

/** A genuine milestone (stage complete, badge earned). Reserved; never for routine clicks. */
export function milestone(el: Target): JSAnimation | null {
  return run(el, {
    scale: [0.85, 1.04, 1],
    opacity: [0, 1],
    duration: MOTION.milestone,
    ease: EASE.out,
  });
}

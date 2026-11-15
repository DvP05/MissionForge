"use client";

import { Activity } from "lucide-react";
import { useEffect, useSyncExternalStore } from "react";

import { readMotionPref, writeMotionPref, type MotionPref } from "@/lib/motion/motion";

const subscribe = (cb: () => void) => {
  window.addEventListener("missionforge:motion", cb);
  return () => window.removeEventListener("missionforge:motion", cb);
};

/** The player's motion preference ("system" follows the OS; "reduced" turns animation off). */
export function useMotionPref(): MotionPref {
  return useSyncExternalStore(subscribe, readMotionPref, () => "system");
}

/** Accessibility setting in the top bar: reduce motion regardless of the OS setting. */
export function MotionToggle() {
  const pref = useMotionPref();
  useEffect(() => {
    document.documentElement.dataset.motion = pref;
  }, [pref]);
  const reduced = pref === "reduced";
  return (
    <button
      type="button"
      data-testid="motion-toggle"
      aria-pressed={reduced}
      onClick={() => writeMotionPref(reduced ? "system" : "reduced")}
      className="btn btn-tertiary min-h-8 px-2 text-xs"
      title="Reduce motion"
    >
      <Activity aria-hidden className="h-3.5 w-3.5" />
      {reduced ? "Motion: reduced" : "Motion: system"}
    </button>
  );
}

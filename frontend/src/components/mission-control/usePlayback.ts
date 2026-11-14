"use client";

import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import {
  advance,
  nextDecisionDay,
  nextEventDay,
  pendingDecision,
  runDuration,
  sortedEvents,
  type MissionEvent,
  type MissionRun,
  type Speed,
} from "./playback";

const REDUCED_QUERY = "(prefers-reduced-motion: reduce)";

/** True when the user asked for reduced motion: no auto-animation, step controls only. */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(
    (notify) => {
      const mq = window.matchMedia(REDUCED_QUERY);
      mq.addEventListener("change", notify);
      return () => mq.removeEventListener("change", notify);
    },
    () => window.matchMedia(REDUCED_QUERY).matches,
    () => false,
  );
}

export interface Playback {
  events: MissionEvent[];
  duration: number;
  day: number;
  playing: boolean;
  speed: Speed;
  reducedMotion: boolean;
  pending: MissionEvent | null;
  atEnd: boolean;
  hasNextDecision: boolean;
  hasNextEvent: boolean;
  play: () => void;
  pause: () => void;
  setSpeed: (s: Speed) => void;
  skipToNextDecision: () => void;
  skipToEnd: () => void;
  step: () => void;
}

/**
 * Client-side iterator over the immutable run. The position is display state only;
 * speed changes pacing, never the run's content, and no outcome is decided here.
 */
export function usePlayback(run: MissionRun, startDay: number): Playback {
  const events = useMemo(() => sortedEvents(run), [run]);
  const duration = useMemo(() => runDuration(run), [run]);
  const reducedMotion = useReducedMotion();
  const [day, setDay] = useState(() => Math.min(Math.max(startDay, 0), duration));
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<Speed>(1);
  const [armed, setArmed] = useState(true);
  const dayRef = useRef(day);
  const speedRef = useRef(speed);
  useEffect(() => {
    speedRef.current = speed;
  }, [speed]);

  const move = useCallback((d: number) => {
    dayRef.current = d;
    setDay(d);
  }, []);

  const pending = pendingDecision(events, run.decisions, day, armed);
  const atEnd = day >= duration;

  useEffect(() => {
    if (!playing || reducedMotion) return;
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min((now - last) / 1000, 0.25);
      last = now;
      const r = advance({
        day: dayRef.current,
        dtSeconds: dt,
        speed: speedRef.current,
        duration,
        events,
        decisions: run.decisions,
        armed,
      });
      move(r.day);
      if (r.stoppedAtDecision || r.finished) setPlaying(false);
      else raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, reducedMotion, duration, events, run.decisions, armed, move]);

  const play = useCallback(() => {
    if (reducedMotion || pending) return;
    if (dayRef.current >= duration) {
      move(0);
      setArmed(true);
    }
    setPlaying(true);
  }, [reducedMotion, pending, duration, move]);

  const nextDecision = armed ? nextDecisionDay(events, run.decisions, day) : null;
  const nextEvent = nextEventDay(events, day);

  return {
    events,
    duration,
    day,
    playing,
    speed,
    reducedMotion,
    pending,
    atEnd,
    hasNextDecision: nextDecision !== null && !pending,
    hasNextEvent: nextEvent !== null && !pending,
    play,
    pause: () => setPlaying(false),
    setSpeed,
    skipToNextDecision: () => {
      if (nextDecision === null || pending) return;
      setPlaying(false);
      move(nextDecision);
    },
    skipToEnd: () => {
      setPlaying(false);
      setArmed(false);
      move(duration);
    },
    step: () => {
      if (pending) return;
      const target = nextEvent;
      if (target === null) return;
      const stop = armed ? nextDecision : null;
      move(stop !== null && stop < target ? stop : target);
    },
  };
}

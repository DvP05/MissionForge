"use client";

import { useCallback, useSyncExternalStore } from "react";

/**
 * Per-browser learning state (concept cards, predictions, pre/post checks). Stored only in
 * this browser's localStorage, never sent anywhere. Safe when storage is unavailable
 * (private mode, blocked site data): reads fall back to null and writes are ignored.
 */
const EVENT = "missionforge:learning";

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writeLocal(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    // storage unavailable: the UI still updates for this page view via the event below
  }
  window.dispatchEvent(new CustomEvent(EVENT, { detail: { key, value } }));
}

const session = new Map<string, string | null>();

function subscribe(onChange: () => void): () => void {
  const handler = (e: Event) => {
    const detail = (e as CustomEvent<{ key: string; value: string | null }>).detail;
    if (detail) session.set(detail.key, detail.value);
    onChange();
  };
  window.addEventListener(EVENT, handler);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(EVENT, handler);
    window.removeEventListener("storage", onChange);
  };
}

/** [value, setValue]; value is null on the server and before anything was stored. */
export function useLocalValue(key: string): [string | null, (value: string | null) => void] {
  const value = useSyncExternalStore(
    subscribe,
    () => {
      const stored = read(key);
      return stored !== null ? stored : (session.get(key) ?? null);
    },
    () => null,
  );
  const set = useCallback((v: string | null) => writeLocal(key, v), [key]);
  return [value, set];
}

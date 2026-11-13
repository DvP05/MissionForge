"use client";

import { Info } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { FidelityBadge } from "@/components/common/FidelityBadge";
import type { components } from "@/lib/api/schema";

export type Provenance = components["schemas"]["Provenance"];

function safeHref(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.href : null;
  } catch {
    return null;
  }
}

/** Keyboard-accessible disclosure of where a value came from. Presentational. */
export function ProvenancePopover({
  provenance,
  label = "this value",
}: {
  provenance: Provenance;
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const root = useRef<HTMLSpanElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        trigger.current?.focus();
      }
    };
    const onPointer = (event: MouseEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onPointer);
    };
  }, [open]);

  const href = safeHref(provenance.sourceUrl);
  const rows: [string, string | null | undefined][] = [
    ["Version", provenance.sourceVersion],
    ["Published", provenance.publishedAt],
    ["Retrieved", provenance.retrievedAt],
  ];

  return (
    <span ref={root} className="relative inline-block">
      <button
        ref={trigger}
        type="button"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        aria-label={`Show provenance for ${label}`}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex h-6 w-6 items-center justify-center rounded-full border border-border text-muted hover:text-foreground"
      >
        <Info aria-hidden className="h-3.5 w-3.5" />
      </button>
      {open ? (
        <div
          id={panelId}
          role="group"
          aria-label={`Provenance for ${label}`}
          data-testid="provenance-panel"
          className="absolute left-0 top-8 z-20 w-72 max-w-[calc(100vw-2rem)] space-y-2 rounded-lg border border-border bg-surface p-3 text-xs shadow-lg"
        >
          <FidelityBadge fidelity={provenance.fidelity} />
          <dl className="space-y-1">
            <div>
              <dt className="text-muted">Source</dt>
              <dd className="break-words text-foreground">
                {href ? (
                  <a href={href} target="_blank" rel="noopener noreferrer" className="underline">
                    {provenance.sourceName}
                  </a>
                ) : (
                  provenance.sourceName
                )}
              </dd>
            </div>
            {rows.map(([name, value]) =>
              value ? (
                <div key={name}>
                  <dt className="text-muted">{name}</dt>
                  <dd className="break-words text-foreground">{value}</dd>
                </div>
              ) : null,
            )}
            <div>
              <dt className="text-muted">Assumptions</dt>
              <dd className="text-foreground">
                {provenance.assumptions && provenance.assumptions.length > 0 ? (
                  <ul className="list-disc space-y-0.5 pl-4">
                    {provenance.assumptions.map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                ) : (
                  "None recorded"
                )}
              </dd>
            </div>
          </dl>
        </div>
      ) : null}
    </span>
  );
}

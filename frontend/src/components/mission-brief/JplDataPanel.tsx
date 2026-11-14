"use client";

import { useEffect, useState } from "react";

import { apiGet } from "@/lib/api-client";

type DataState =
  | { kind: "loading" }
  | { kind: "ready"; status: string; records: { option_id: string; time_of_flight_days?: number | null }[]; message?: string | null }
  | { kind: "error"; message: string };

export function JplDataPanel() {
  const [state, setState] = useState<DataState>({ kind: "loading" });

  useEffect(() => {
    let active = true;
    void apiGet("/api/space-data/neo-accessible").then((response) => {
      if (!active) return;
      if (!response.ok || !response.data) {
        setState({ kind: "error", message: response.error?.message ?? "Small-body data unavailable." });
        return;
      }
      setState({
        kind: "ready",
        status: response.data.status,
        records: response.data.records,
        message: response.data.message,
      });
    });
    return () => {
      active = false;
    };
  }, []);

  return (
    <section aria-labelledby="jpl-data-heading" className="space-y-2 rounded-lg border border-border p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="jpl-data-heading" className="text-sm font-semibold">Small-body mission design data</h2>
        {state.kind === "ready" ? (
          <span className="rounded-full border border-border px-2 py-0.5 text-xs uppercase">{state.status}</span>
        ) : null}
      </div>
      {state.kind === "loading" ? <p className="text-sm text-muted">Loading server-side source data…</p> : null}
      {state.kind === "error" ? <p role="alert" className="text-sm text-accent-amber">{state.message}</p> : null}
      {state.kind === "ready" ? (
        <>
          <p className="text-xs text-muted">
            Data is normalized by MISSIONFORGE. The browser never calls JPL directly.
          </p>
          <ul className="space-y-1 text-sm">
            {state.records.map((record) => (
              <li key={record.option_id}>
                <span className="font-medium">{record.option_id}</span>
                {record.time_of_flight_days == null ? "" : ` · ${record.time_of_flight_days} days flight time`}
              </li>
            ))}
          </ul>
          {state.message ? <p className="text-xs text-muted">{state.message}</p> : null}
        </>
      ) : null}
    </section>
  );
}

"use client";

import { Radio, Telescope } from "lucide-react";
import { useEffect } from "react";

import { formatNumber, formatQuantity, MISSING } from "@/lib/format";
import { constraintStatus } from "@/lib/spacecraft/engineering-status";
import { useArchitectUi } from "@/state/architect-ui-store";
import { useMissionStore, type MissionState } from "@/state/mission-store";
import type { CatalogComponent } from "./catalog-helpers";
import { EngStatusChip } from "./EngStatusChip";

const RATES = [8_000, 25_000, 50_000, 100_000, 250_000, 500_000, 1_000_000, 2_000_000, 5_000_000];
const PASSES = [15, 30, 45, 60, 90, 120, 180, 240, 360, 480];
const DUTY_SCALES = [0.5, 0.6, 0.7, 0.8, 0.9, 1, 1.1, 1.25, 1.5];

const rateLabel = (bps: number) => (bps >= 1e6 ? `${formatNumber(bps / 1e6)} Mbit/s` : `${formatNumber(bps / 1e3)} kbit/s`);

function commit(change: (ops: MissionState["operations"]) => Partial<MissionState["operations"]>) {
  const store = useMissionStore.getState();
  if (!store.mission) return;
  store.updateOperations(change(store.mission.operations));
  store.commitRevision();
}

/**
 * Operations plan (prod.md 522: "change the observing duty cycle or communications
 * architecture"). The downlink rate, pass length and observation duty cycle are the levers
 * that resolve a data-return shortfall; each change is one design revision analysed by the
 * engine. The engine clips every contact to the radio's maximum rate, so rates above it are not
 * offered. Results shown here are the engine's data-return constraint, never a browser estimate.
 */
export function OperationsPanel({ mission, index }: { mission: MissionState; index: Map<string, CatalogComponent> }) {
  // arriving from the readiness review ("fix it in the architect"): bring this panel into view
  useEffect(() => {
    if (window.location.hash !== "#ops-heading") return;
    // on narrow screens this panel lives in the Spacecraft tab: show it first
    useArchitectUi.getState().setMobileTab("spacecraft");
    // the router's own scroll-to-top and the 3D viewport loading above can move the page after
    // mount, so settle the scroll once more when they are done
    const go = () => document.getElementById("ops-heading")?.scrollIntoView({ block: "center" });
    const timers = [100, 700, 1500].map((ms) => window.setTimeout(go, ms));
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, []);
  const analysis = useMissionStore((s) => s.analysis);
  const analysisRevision = useMissionStore((s) => s.analysisRevision);
  const ops = mission.operations;
  const radio = index.get(mission.architecture.communicationsId);
  const radioMax = radio?.parameters.max_data_rate?.value ?? null;
  const contacts = ops.downlinkPlan;
  const rate = contacts.length ? Math.max(...contacts.map((c) => c.dataRateBitsPerSecond)) : null;
  const pass = contacts.length ? contacts[0].durationMinutes : null;
  const uniformPass = contacts.every((c) => c.durationMinutes === pass);
  const meanDuty = ops.observationPlan.length
    ? ops.observationPlan.reduce((s, o) => s + o.dutyCycle, 0) / ops.observationPlan.length
    : null;
  const current = analysis !== null && analysisRevision === mission.designRevision;
  const dataReturn = current ? analysis.constraints.find((c) => c.id === "data-return") : undefined;
  const clipped = rate !== null && radioMax !== null && rate > radioMax;
  const rateOptions = [...new Set([...RATES.filter((r) => radioMax === null || r <= radioMax), ...(rate ? [rate] : [])])].sort((a, b) => a - b);

  return (
    <section aria-labelledby="ops-heading" data-testid="operations-panel" className="panel space-y-3 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="ops-heading" className="font-mono text-xs uppercase tracking-[0.2em] text-primary">
          Operations plan · downlink and observing
        </h2>
        {dataReturn ? (
          <span className="flex items-center gap-2 text-xs text-muted">
            Data return <EngStatusChip status={constraintStatus(dataReturn)} testId="ops-data-return" />
          </span>
        ) : null}
      </div>
      {dataReturn && dataReturn.status !== "pass" ? <p className="text-xs text-muted">{dataReturn.explanation}</p> : null}

      <div className="grid gap-3 sm:grid-cols-3">
        <label className="space-y-1 text-sm">
          <span className="flex items-center gap-1.5 text-xs text-muted">
            <Radio aria-hidden className="h-3.5 w-3.5" /> Downlink rate per contact
          </span>
          <select
            data-testid="ops-rate"
            value={rate ?? ""}
            disabled={!contacts.length}
            onChange={(e) => {
              const v = Number(e.target.value);
              commit((o) => ({ downlinkPlan: o.downlinkPlan.map((c) => ({ ...c, dataRateBitsPerSecond: v })) }));
            }}
            className="min-h-10 w-full border border-border bg-background-2 px-2 font-mono text-sm"
          >
            {rateOptions.map((r) => (
              <option key={r} value={r}>
                {rateLabel(r)}
              </option>
            ))}
          </select>
          <span className="block text-[11px] text-muted">
            Radio maximum: {radioMax === null ? MISSING : rateLabel(radioMax)}
            {clipped ? " · above it, the engine clips each contact to the radio's rate" : ""}
          </span>
        </label>

        <label className="space-y-1 text-sm">
          <span className="text-xs text-muted">Pass length ({contacts.length} planned contacts)</span>
          <select
            data-testid="ops-pass"
            value={uniformPass && pass !== null ? pass : ""}
            disabled={!contacts.length}
            onChange={(e) => {
              const v = Number(e.target.value);
              commit((o) => ({ downlinkPlan: o.downlinkPlan.map((c) => ({ ...c, durationMinutes: v })) }));
            }}
            className="min-h-10 w-full border border-border bg-background-2 px-2 font-mono text-sm"
          >
            {!uniformPass ? <option value="">mixed</option> : null}
            {[...new Set([...PASSES, ...(pass ? [pass] : [])])].sort((a, b) => a - b).map((p) => (
              <option key={p} value={p}>
                {p} min
              </option>
            ))}
          </select>
          <span className="block text-[11px] text-muted">Longer passes cost ground-station time in operations.</span>
        </label>

        <label className="space-y-1 text-sm">
          <span className="flex items-center gap-1.5 text-xs text-muted">
            <Telescope aria-hidden className="h-3.5 w-3.5" /> Observation duty cycle
          </span>
          <select
            data-testid="ops-duty"
            value=""
            disabled={!ops.observationPlan.length}
            onChange={(e) => {
              const k = Number(e.target.value);
              if (!k) return;
              commit((o) => ({
                observationPlan: o.observationPlan.map((it) => ({ ...it, dutyCycle: Math.min(1, it.dutyCycle * k) })),
              }));
            }}
            className="min-h-10 w-full border border-border bg-background-2 px-2 font-mono text-sm"
          >
            <option value="">now {meanDuty === null ? MISSING : `${formatNumber(meanDuty * 100)} %`} · scale by…</option>
            {DUTY_SCALES.filter((k) => k !== 1).map((k) => (
              <option key={k} value={k}>
                × {k} ({k < 1 ? "less data, less science" : "more data, more science"})
              </option>
            ))}
          </select>
          <span className="block text-[11px] text-muted">Observing less returns less science; the engine re-scores coverage.</span>
        </label>
      </div>

      {dataReturn?.actual && dataReturn.limit ? (
        <p className="font-mono text-xs text-muted">
          Engine: downlinked {formatQuantity(dataReturn.actual)} · needed {formatQuantity(dataReturn.limit)} (revision {mission.designRevision})
        </p>
      ) : null}
    </section>
  );
}

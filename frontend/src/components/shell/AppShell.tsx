import { Menu, Rocket } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { BackendHealthProvider } from "@/components/shell/BackendHealth";
import { BackendStatus, OfflineBanner } from "@/components/shell/BackendStatus";
import { Disclaimer } from "@/components/shell/Disclaimer";
import { MotionToggle } from "@/components/shell/MotionToggle";
import { StationRail } from "@/components/shell/StationRail";
import { TelemetryBar } from "@/components/shell/TelemetryBar";

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2" aria-label="MISSIONFORGE home">
      <span aria-hidden className="grid h-8 w-8 place-items-center bg-elevated">
        <Rocket className="h-4 w-4 text-primary" />
      </span>
      <span className="flex flex-col">
        <span className="font-mono text-xs font-semibold uppercase tracking-[0.2em] text-primary">MISSIONFORGE</span>
        <span className="font-mono text-[10px] text-faint">mission design console</span>
      </span>
    </Link>
  );
}

/**
 * Command shell (Stitch "Aerospace Mission Telemetry & Command System"): a fixed station rail on
 * desktop, a telemetry strip across the top, the HUD datum grid behind everything. On narrow
 * screens the rail folds into a Stations menu.
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <BackendHealthProvider>
      <div aria-hidden className="space-backdrop" />
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <div className="lg:grid lg:min-h-screen lg:grid-cols-[16rem_minmax(0,1fr)]">
        <aside className="hidden border-r border-border bg-surface lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col lg:justify-between">
          <div>
            <div className="flex h-16 items-center bg-background-2 px-4">
              <Brand />
            </div>
            <div className="flex items-center justify-between bg-background-2 px-4 py-1.5">
              <span className="label-caps text-muted">Stations</span>
              <span className="label-caps text-primary">Journey</span>
            </div>
            <StationRail />
          </div>
          <div className="space-y-1 bg-background-2 p-3">
            <span className="label-caps block text-muted">Educational prototype</span>
            <span className="block text-[11px] text-faint">Not a NASA or JPL product.</span>
          </div>
        </aside>

        <div className="flex min-h-screen min-w-0 flex-col">
          <header className="sticky top-0 z-30 border-b border-border bg-background-2/95 backdrop-blur">
            <div className="flex min-h-16 flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-2 sm:px-6">
              <div className="flex min-w-0 items-center gap-3">
                <details className="relative lg:hidden">
                  <summary className="btn btn-tertiary min-h-9 list-none px-2.5" aria-label="Stations menu" data-testid="stations-menu">
                    <Menu aria-hidden className="h-4 w-4" /> Stations
                  </summary>
                  <div className="absolute left-0 z-50 mt-2 w-64 border border-border bg-surface shadow-[2px_2px_0_#070808]">
                    <StationRail />
                  </div>
                </details>
                <span className="lg:hidden">
                  <Brand />
                </span>
                <div className="hidden min-w-0 md:block">
                  <TelemetryBar />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <MotionToggle />
                <BackendStatus />
              </div>
            </div>
          </header>
          <OfflineBanner />
          <main id="main" className="w-full max-w-[100rem] flex-1 px-4 py-6 sm:px-6 lg:py-8">
            {children}
          </main>
          <Disclaimer />
        </div>
      </div>
    </BackendHealthProvider>
  );
}

import Link from "next/link";
import type { ReactNode } from "react";

import { BackendHealthProvider } from "@/components/shell/BackendHealth";
import { BackendStatus, OfflineBanner } from "@/components/shell/BackendStatus";
import { Disclaimer } from "@/components/shell/Disclaimer";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <BackendHealthProvider>
      <div className="flex min-h-screen flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2"
        >
          Skip to content
        </a>
        <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-border bg-surface px-4 py-3 sm:px-6">
          <Link
            href="/"
            className="font-mono text-sm tracking-[0.2em] text-accent-cyan"
            aria-label="MISSIONFORGE home"
          >
            MISSIONFORGE
          </Link>
          <nav aria-label="Site" className="flex items-center gap-4 text-sm">
            <Link href="/about" className="text-muted hover:text-foreground">
              About
            </Link>
            <BackendStatus />
          </nav>
        </header>
        <OfflineBanner />
        <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 sm:py-12">
          {children}
        </main>
        <Disclaimer />
      </div>
    </BackendHealthProvider>
  );
}

import type { ReactNode } from "react";

import { BackendStatus } from "@/components/shell/BackendStatus";
import { Disclaimer } from "@/components/shell/Disclaimer";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between border-b border-border bg-surface px-6 py-3">
        <span className="font-mono text-sm tracking-[0.2em] text-accent-cyan">
          MISSIONFORGE
        </span>
        <BackendStatus />
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-16">{children}</main>
      <Disclaimer />
    </div>
  );
}

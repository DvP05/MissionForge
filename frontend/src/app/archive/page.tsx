import type { Metadata } from "next";

import { MissionArchive } from "@/components/persistence/MissionArchive";

export const metadata: Metadata = { title: "Mission archive · MISSIONFORGE" };

export default function ArchivePage() {
  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-accent-amber">Mission archive</p>
        <h1 className="text-3xl font-semibold tracking-tight">Saved architectures and flown missions</h1>
        <p className="max-w-2xl text-sm text-muted">
          Everything here is stored in this browser only. Runs are recorded engine outputs; export a package from a
          mission to keep it or move it to another machine.
        </p>
      </header>
      <MissionArchive />
    </div>
  );
}

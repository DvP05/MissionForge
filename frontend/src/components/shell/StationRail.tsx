"use client";

import {
  Archive,
  ClipboardCheck,
  Compass,
  FlaskConical,
  Info,
  LayoutGrid,
  LineChart,
  Radar,
  Rocket,
  Scale,
  Shapes,
} from "lucide-react";
import Link from "next/link";
import { focusLaunchSoon } from "@/lib/launch-focus";
import { usePathname } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";

import { STORAGE_CHANGED_EVENT } from "@/lib/persistence/events";
import { ACTIVE_MISSION_EVENT, readActiveMission } from "@/lib/persistence/active-mission";
import { listCachedRuns } from "@/lib/persistence/run-cache";
import { useMissionStore } from "@/state/mission-store";

const subscribe = (cb: () => void) => {
  window.addEventListener(ACTIVE_MISSION_EVENT, cb);
  window.addEventListener("storage", cb);
  return () => {
    window.removeEventListener(ACTIVE_MISSION_EVENT, cb);
    window.removeEventListener("storage", cb);
  };
};

/** Active mission id (open mission first, else the last one worked on) and its latest run. */
function useStationContext(pathname: string): { missionId: string | null; runId: string | null } {
  const open = useMissionStore((s) => s.mission?.missionId ?? null);
  const last = useSyncExternalStore(subscribe, readActiveMission, () => null);
  const missionId = open ?? last;
  const [runId, setRunId] = useState<string | null>(null);
  useEffect(() => {
    const read = () => {
      const runs = missionId ? listCachedRuns(missionId) : [];
      runs.sort((a, b) => a.run.designRevision - b.run.designRevision);
      setRunId(runs.at(-1)?.run.runId ?? null);
    };
    read();
    window.addEventListener(STORAGE_CHANGED_EVENT, read);
    return () => window.removeEventListener(STORAGE_CHANGED_EVENT, read);
    // pathname: a launch caches its run and then navigates, so re-read on every navigation
  }, [missionId, pathname]);
  return { missionId, runId };
}

interface Station {
  key: string;
  label: string;
  icon: typeof Rocket;
  href: (m: string | null, r: string | null) => string;
  match: (p: string) => boolean;
  /** Why the link falls back (no mission / not flown); shown to screen readers and on hover. */
  fallback?: (m: string | null, r: string | null) => string | null;
}

const needMission = (m: string | null) => (m ? null : "No active mission yet: choose a scenario in the command centre.");
const needRun = (m: string | null, r: string | null) =>
  !m ? needMission(m) : r ? null : "Not flown yet: opens the launch panel in the architect.";

const STATIONS: Station[] = [
  { key: "command", label: "Command centre", icon: LayoutGrid, href: () => "/", match: (p) => p === "/" },
  { key: "briefing", label: "Mission briefing", icon: Compass, href: (m) => (m ? `/mission/${m}` : "/#scenarios-heading"), match: (p) => p.startsWith("/mission/"), fallback: needMission },
  { key: "science", label: "Science lab", icon: FlaskConical, href: (m) => (m ? `/science/${m}` : "/#scenarios-heading"), match: (p) => p.startsWith("/science/"), fallback: needMission },
  { key: "architect", label: "Mission architect", icon: Shapes, href: (m) => (m ? `/architect/${m}` : "/#scenarios-heading"), match: (p) => p.startsWith("/architect/"), fallback: needMission },
  { key: "trade", label: "Trade study", icon: Scale, href: (m) => (m ? `/arena/${m}` : "/#scenarios-heading"), match: (p) => p.startsWith("/arena/"), fallback: needMission },
  { key: "readiness", label: "Readiness review", icon: ClipboardCheck, href: (m) => (m ? `/readiness/${m}` : "/#scenarios-heading"), match: (p) => p.startsWith("/readiness/"), fallback: needMission },
  { key: "control", label: "Mission control", icon: Radar, href: (m, r) => (r ? `/control/${r}` : m ? `/architect/${m}#launch` : "/#scenarios-heading"), match: (p) => p.startsWith("/control/"), fallback: needRun },
  { key: "debrief", label: "Mission debrief", icon: LineChart, href: (m, r) => (r ? `/review/${r}` : m ? `/architect/${m}#launch` : "/#scenarios-heading"), match: (p) => p.startsWith("/review/"), fallback: needRun },
  { key: "hangar", label: "Blueprints hangar", icon: Archive, href: () => "/archive", match: (p) => p.startsWith("/archive") },
  { key: "about", label: "About", icon: Info, href: () => "/about", match: (p) => p.startsWith("/about") },
];

/**
 * Station rail (Stitch "BUS::NAV_CHANNEL"): every destination of the mission journey, always
 * clickable. Mission stations follow the active mission; before a flight, Mission control and
 * Debrief open the launch panel and say so. Active station: signal-amber bar.
 */
export function StationRail({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname() ?? "/";
  const { missionId, runId } = useStationContext(pathname);
  return (
    <nav aria-label="Stations" data-testid="station-rail" className="flex flex-col gap-0.5 p-1">
      {STATIONS.map((s) => {
        const active = s.match(pathname);
        const Icon = s.icon;
        const note = s.fallback?.(missionId, runId) ?? null;
        return (
          <Link
            key={s.key}
            href={s.href(missionId, runId)}
            onClick={() => {
              onNavigate?.();
              if (s.href(missionId, runId).endsWith("#launch")) focusLaunchSoon();
            }}
            aria-current={active ? "page" : undefined}
            title={note ?? undefined}
            data-testid={`station-${s.key}`}
            className={`flex min-h-10 items-center gap-2.5 border-l-2 px-3 text-sm uppercase tracking-wide ${
              active
                ? "border-signal bg-signal/15 font-semibold text-signal"
                : "border-transparent text-muted hover:bg-elevated hover:text-foreground"
            }`}
          >
            <Icon aria-hidden className="h-4 w-4 shrink-0" />
            <span className="min-w-0 flex-1 truncate">{s.label}</span>
            {note ? <span className="label-caps text-faint" aria-hidden>{s.key === "control" || s.key === "debrief" ? (missionId ? "launch" : "—") : "—"}</span> : null}
            {note ? <span className="sr-only">: {note}</span> : null}
          </Link>
        );
      })}
    </nav>
  );
}

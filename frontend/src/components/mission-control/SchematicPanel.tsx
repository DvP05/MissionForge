import type { components } from "@/lib/api/schema";
import { MissionVisualization } from "@/components/visualization/MissionVisualization";
import { type Phase } from "./playback";

type MissionState = components["schemas"]["MissionState"];

export function SchematicPanel({ mission, phase, day }: { mission: MissionState; phase: Phase | null; day: number }) {
  return <MissionVisualization mission={mission} phase={phase} day={day} />;
}

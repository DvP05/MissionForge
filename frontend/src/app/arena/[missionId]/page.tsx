import { CompareView } from "@/components/arena/CompareView";
import { AdvancedMissionLab } from "@/components/arena/AdvancedMissionLab";
import { MissionWorkspace } from "@/components/workspace/MissionWorkspace";

/** Arena: trade-study compare view (Task 3.5). Robustness and Pareto views arrive in later tasks. */
export default async function ArenaPage({ params }: { params: Promise<{ missionId: string }> }) {
  const { missionId } = await params;
  return (
    <MissionWorkspace missionId={missionId} view="arena">
      <CompareView />
      <AdvancedMissionLab />
    </MissionWorkspace>
  );
}

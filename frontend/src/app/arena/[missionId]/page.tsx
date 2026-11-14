import { CompareView } from "@/components/arena/CompareView";
import { ParetoExplorer } from "@/components/arena/ParetoExplorer";
import { RobustnessLab } from "@/components/robustness/RobustnessLab";
import { MissionWorkspace } from "@/components/workspace/MissionWorkspace";

/** Arena: design arena (Task 6.2), robustness lab (Task 6.3) and trade-study compare (Task 3.5). */
export default async function ArenaPage({ params }: { params: Promise<{ missionId: string }> }) {
  const { missionId } = await params;
  return (
    <MissionWorkspace missionId={missionId} view="arena">
      <div className="space-y-8">
        <ParetoExplorer />
        <RobustnessLab />
        <CompareView />
      </div>
    </MissionWorkspace>
  );
}

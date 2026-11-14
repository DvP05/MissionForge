import { MissionBrief } from "@/components/mission-brief/MissionBrief";
import { BeliefTracker } from "@/components/science-evidence/BeliefTracker";
import { MissionWorkspace } from "@/components/workspace/MissionWorkspace";

export default async function MissionBriefPage({ params }: { params: Promise<{ missionId: string }> }) {
  const { missionId } = await params;
  return (
    <MissionWorkspace missionId={missionId} view="brief">
      <div className="space-y-8">
        <MissionBrief />
        <BeliefTracker />
      </div>
    </MissionWorkspace>
  );
}

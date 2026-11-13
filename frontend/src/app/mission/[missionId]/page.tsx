import { MissionBrief } from "@/components/mission-brief/MissionBrief";
import { MissionWorkspace } from "@/components/workspace/MissionWorkspace";

export default async function MissionBriefPage({ params }: { params: Promise<{ missionId: string }> }) {
  const { missionId } = await params;
  return (
    <MissionWorkspace missionId={missionId} view="brief">
      <MissionBrief />
    </MissionWorkspace>
  );
}

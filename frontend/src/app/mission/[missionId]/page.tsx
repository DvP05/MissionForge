import { Placeholder } from "@/components/workspace/Placeholder";
import { MissionWorkspace } from "@/components/workspace/MissionWorkspace";

export default async function MissionBriefPage({ params }: { params: Promise<{ missionId: string }> }) {
  const { missionId } = await params;
  return (
    <MissionWorkspace missionId={missionId} view="brief">
      <Placeholder
        title="Mission brief"
        message="The brief, objectives and constraints editor arrive in the next build step."
      />
    </MissionWorkspace>
  );
}

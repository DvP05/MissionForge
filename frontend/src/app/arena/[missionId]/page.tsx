import { Placeholder } from "@/components/workspace/Placeholder";
import { MissionWorkspace } from "@/components/workspace/MissionWorkspace";

export default async function ArenaPage({ params }: { params: Promise<{ missionId: string }> }) {
  const { missionId } = await params;
  return (
    <MissionWorkspace missionId={missionId} view="arena">
      <Placeholder
        title="Design arena"
        message="Trade studies and robustness checks arrive in a later build step."
      />
    </MissionWorkspace>
  );
}

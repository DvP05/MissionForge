import { ArchitectPage } from "@/components/architect/ArchitectPage";
import { MissionWorkspace } from "@/components/workspace/MissionWorkspace";

export default async function Page({ params }: { params: Promise<{ missionId: string }> }) {
  const { missionId } = await params;
  return (
    <MissionWorkspace missionId={missionId} view="architect">
      <ArchitectPage />
    </MissionWorkspace>
  );
}

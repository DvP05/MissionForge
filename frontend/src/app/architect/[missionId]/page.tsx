import { Placeholder } from "@/components/workspace/Placeholder";
import { MissionWorkspace } from "@/components/workspace/MissionWorkspace";

export default async function ArchitectPage({ params }: { params: Promise<{ missionId: string }> }) {
  const { missionId } = await params;
  return (
    <MissionWorkspace missionId={missionId} view="architect">
      <Placeholder
        title="Architect"
        message="Subsystem selection and live budgets arrive in a later build step."
      />
    </MissionWorkspace>
  );
}

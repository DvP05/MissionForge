import { ReadinessReview } from "@/components/readiness/ReadinessReview";
import { MissionWorkspace } from "@/components/workspace/MissionWorkspace";

export default async function Page({ params }: { params: Promise<{ missionId: string }> }) {
  const { missionId } = await params;
  return (
    <MissionWorkspace missionId={missionId} view="readiness">
      <ReadinessReview />
    </MissionWorkspace>
  );
}

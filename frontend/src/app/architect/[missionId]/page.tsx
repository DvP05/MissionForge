import { Placeholder } from "@/components/workspace/Placeholder";
import { MissionWorkspace } from "@/components/workspace/MissionWorkspace";

export default function ArchitectPage() {
  return (
    <MissionWorkspace view="architect">
      <Placeholder
        title="Architect"
        message="Subsystem selection and live budgets arrive in a later build step."
      />
    </MissionWorkspace>
  );
}

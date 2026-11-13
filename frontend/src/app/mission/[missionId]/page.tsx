import { Placeholder } from "@/components/workspace/Placeholder";
import { MissionWorkspace } from "@/components/workspace/MissionWorkspace";

export default function MissionBriefPage() {
  return (
    <MissionWorkspace view="brief">
      <Placeholder
        title="Mission brief"
        message="The brief, objectives and constraints editor arrive in the next build step."
      />
    </MissionWorkspace>
  );
}

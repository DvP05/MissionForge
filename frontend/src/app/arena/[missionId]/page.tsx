import { Placeholder } from "@/components/workspace/Placeholder";
import { MissionWorkspace } from "@/components/workspace/MissionWorkspace";

export default function ArenaPage() {
  return (
    <MissionWorkspace view="arena">
      <Placeholder
        title="Design arena"
        message="Trade studies and robustness checks arrive in a later build step."
      />
    </MissionWorkspace>
  );
}

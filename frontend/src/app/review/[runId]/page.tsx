import { NotFoundState } from "@/components/common/States";

// Simulation runs are not persisted yet; until a run store exists every run ID is unknown.
export default function ReviewPage() {
  return (
    <NotFoundState
      title="Run not found"
      message="No simulation run with this ID exists in this browser yet."
    />
  );
}

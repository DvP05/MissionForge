"use client";

import { RunGate } from "@/components/mission-control/RunGate";
import { ReviewPage } from "./ReviewPage";

export function ReviewRoute({ runId }: { runId: string }) {
  return <RunGate runId={runId}>{(data) => <ReviewPage data={data} />}</RunGate>;
}

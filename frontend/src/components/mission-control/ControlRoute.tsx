"use client";

import { MissionControl } from "./MissionControl";
import { RunGate } from "./RunGate";

export function ControlRoute({ runId, startDay }: { runId: string; startDay: number }) {
  return <RunGate runId={runId}>{(data) => <MissionControl key={data.run.runId} data={data} startDay={startDay} />}</RunGate>;
}

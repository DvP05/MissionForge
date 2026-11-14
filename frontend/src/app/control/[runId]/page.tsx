import { ControlRoute } from "@/components/mission-control/ControlRoute";

export default async function ControlPage({
  params,
  searchParams,
}: {
  params: Promise<{ runId: string }>;
  searchParams: Promise<{ day?: string }>;
}) {
  const { runId } = await params;
  const { day } = await searchParams;
  const parsed = Number(day);
  const startDay = Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
  return <ControlRoute runId={runId} startDay={startDay} />;
}

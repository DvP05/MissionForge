import { ReviewRoute } from "@/components/review/ReviewRoute";

export default async function Page({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  return <ReviewRoute runId={runId} />;
}

"use client";

import { ErrorState } from "@/components/common/States";

export default function RouteError({ reset }: { error: Error; reset: () => void }) {
  return (
    <ErrorState
      title="This run could not be displayed"
      message="Something went wrong while showing this run. Your design and run are not changed. Try again, or start from the Architect."
      onRetry={reset}
    />
  );
}

import { EmptyState } from "@/components/common/States";

/** Mount point for a feature module that a later task fills in. */
export function Placeholder({ title, message }: { title: string; message: string }) {
  return (
    <div data-testid="view-placeholder">
      <EmptyState title={title} message={message} />
    </div>
  );
}

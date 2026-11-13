import { CircleAlert, Inbox, SearchX } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

function Frame({
  testId,
  icon,
  title,
  children,
  role,
}: {
  testId: string;
  icon: ReactNode;
  title: string;
  children: ReactNode;
  role?: "alert" | "status";
}) {
  return (
    <section
      data-testid={testId}
      role={role}
      className="mx-auto flex max-w-xl flex-col items-start gap-3 rounded-xl border border-border bg-surface p-6"
    >
      <div className="text-accent-amber">{icon}</div>
      <h2 className="text-xl font-semibold">{title}</h2>
      {children}
    </section>
  );
}

export const ACTION_CLASS =
  "inline-flex min-h-11 items-center rounded-lg border border-accent-cyan/60 px-4 text-sm font-medium text-accent-cyan hover:bg-accent-cyan/10";

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div
      data-testid="loading-state"
      role="status"
      aria-busy="true"
      aria-live="polite"
      className="space-y-3"
    >
      <span className="sr-only">{label}</span>
      <div aria-hidden className="h-8 w-2/3 animate-pulse rounded bg-surface motion-reduce:animate-none" />
      <div aria-hidden className="h-24 w-full animate-pulse rounded bg-surface motion-reduce:animate-none" />
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <Frame testId="error-state" role="alert" icon={<CircleAlert aria-hidden className="h-6 w-6" />} title={title}>
      <p className="text-sm text-muted">{message}</p>
      {onRetry ? (
        <button type="button" onClick={onRetry} className={ACTION_CLASS}>
          Retry
        </button>
      ) : null}
    </Frame>
  );
}

export function EmptyState({
  title,
  message,
  action,
}: {
  title: string;
  message: string;
  action?: ReactNode;
}) {
  return (
    <Frame testId="empty-state" icon={<Inbox aria-hidden className="h-6 w-6" />} title={title}>
      <p className="text-sm text-muted">{message}</p>
      {action}
    </Frame>
  );
}

export function NotFoundState({
  title = "Mission not found",
  message = "This mission is not saved in this browser.",
}: {
  title?: string;
  message?: string;
}) {
  return (
    <Frame testId="not-found-state" icon={<SearchX aria-hidden className="h-6 w-6" />} title={title}>
      <p className="text-sm text-muted">{message}</p>
      <Link href="/" className={ACTION_CLASS}>
        Start a mission
      </Link>
    </Frame>
  );
}

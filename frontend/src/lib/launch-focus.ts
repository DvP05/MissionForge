/**
 * Bring the launch control into view and focus it. Used by "launch first" links: Next.js
 * navigates same-page hash links with pushState (no hashchange event), so the link focuses the
 * button itself; on another page the LaunchPanel does it when it mounts.
 */
export function focusLaunchSoon(): void {
  requestAnimationFrame(() => {
    const btn = document.querySelector<HTMLButtonElement>("#launch [data-testid='launch-button']");
    if (!btn) return;
    btn.closest("section")?.scrollIntoView({ block: "center" });
    btn.focus({ preventScroll: true });
  });
}

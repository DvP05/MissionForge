import { expect, test } from "@playwright/test";

/** Stitch command shell: station rail, telemetry strip and the readiness review station. */

test("station rail follows the active mission and never dead-ends", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await expect(page.getByTestId("station-rail").first().getByTestId("station-command")).toHaveAttribute("aria-current", "page");
  await page.getByTestId("scenario-card-neo-rendezvous").getByRole("button", { name: /start mission/i }).click();
  await page.waitForURL(/\/mission\/mission-[0-9a-f]{12}$/);
  const id = new URL(page.url()).pathname.split("/").pop() as string;

  const rail = page.getByTestId("station-rail").first();
  await expect(rail.getByTestId("station-architect")).toHaveAttribute("href", `/architect/${id}`);
  // not flown yet: mission control opens the launch panel instead of nothing
  await expect(rail.getByTestId("station-control")).toHaveAttribute("href", `/architect/${id}#launch`);
  // the telemetry strip only shows real values
  await expect(page.getByTestId("telemetry-target")).not.toBeEmpty();
});

test("readiness review audits every gate from the engine and authorises flight", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("scenario-card-neo-rendezvous").getByRole("button", { name: /start mission/i }).click();
  await page.waitForURL(/\/mission\/mission-[0-9a-f]{12}$/);
  const id = new URL(page.url()).pathname.split("/").pop() as string;
  await page.goto(`/readiness/${id}`);
  const review = page.getByTestId("readiness-review");
  await expect(review).toBeVisible({ timeout: 30_000 });
  // the starter design fails its link: NO-GO, and the engine verdict says not ready
  await expect(page.getByTestId("review-gate-comms")).toHaveAttribute("data-status", "FAIL");
  await expect(page.getByTestId("readiness-verdict")).toContainText(/not mission-ready/i);
  // not modelled is reported as such, never as GO
  await expect(page.getByTestId("review-gate-thermal")).toHaveAttribute("data-status", "NOT MODELLED");
  await expect(review.getByTestId("launch-button")).toBeVisible();
});

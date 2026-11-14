import { expect, test } from "@playwright/test";

/** Task 7.1: Lunar Polar Scout and Earth Observation play end to end like NEO. */

for (const scenario of ["lunar-polar-scout", "earth-observation"] as const) {
  test(`${scenario}: brief, architect, launch, mission control and review`, async ({ page }) => {
    await page.goto("/");
    await page.getByTestId(`scenario-card-${scenario}`).getByRole("button", { name: /start mission/i }).click();
    await page.waitForURL(/\/mission\/mission-[0-9a-f]{12}$/);
    const id = new URL(page.url()).pathname.split("/").pop() as string;
    await expect(page.getByTestId("workspace-title")).toBeVisible();

    await page.goto(`/architect/${id}`);
    await expect(page.getByTestId("analysis-revision")).toContainText(/revision 0/i, { timeout: 30_000 });
    await expect(page.getByTestId("launch-button")).toBeEnabled();
    await page.getByTestId("launch-button").click();
    await page.waitForURL(/\/control\/[^/]+/, { timeout: 30_000 });
    await expect(page.getByTestId("mission-control")).toBeVisible();
    await expect(page.getByTestId("authority-banner")).toBeVisible();

    await page.getByTestId("skip-to-end").click();
    const yes = page.getByTestId("skip-end-confirm-yes");
    if (await yes.isVisible().catch(() => false)) await yes.click();
    await page.getByTestId("open-review").click();
    await page.waitForURL(/\/review\/[^/]+/);
    await expect(page.getByTestId("review-outcome")).toContainText(/objectives achieved/i);
    await expect(page.getByTestId("review-autonomy").getByTestId("autonomy-entry").first()).toBeVisible();
  });
}

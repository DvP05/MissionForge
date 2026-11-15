import { expect, test, type Page } from "@playwright/test";

/** Task 7.2: the 2D mission map is driven by run data, labelled illustrative, text-equivalent. */

async function launch(page: Page, scenario: string, fixComms: boolean): Promise<string> {
  await page.goto("/");
  await page.getByTestId(`scenario-card-${scenario}`).getByRole("button", { name: /start mission/i }).click();
  await page.waitForURL(/\/mission\/mission-[0-9a-f]{12}$/);
  const id = new URL(page.url()).pathname.split("/").pop() as string;
  await page.goto(`/architect/${id}`);
  await expect(page.getByTestId("analysis-revision")).toContainText(/revision 0/i, { timeout: 30_000 });
  if (fixComms) {
    await page.getByTestId("category-nav-communications").click();
    await page.getByTestId("select-comms-xband-medium").click();
    await page.getByTestId("confirm-change").click();
    await expect(page.getByTestId("mission-ready-badge")).toHaveText(/^mission-ready$/i);
  }
  await page.getByTestId("launch-button").click();
  await page.waitForURL(/\/control\/[^/]+/, { timeout: 30_000 });
  return new URL(page.url()).pathname.split("/").pop() as string;
}

test("NEO map: transfer progress moves with the day and shows trajectory data", async ({ page }) => {
  const runId = await launch(page, "neo-rendezvous", true);
  await page.goto(`/control/${runId}?day=100`);
  const map = page.getByTestId("schematic-2d");
  await expect(page.getByTestId("mission-map-text")).toContainText(/in transfer, 36% of the 275-day flight/i);
  const early = await page.getByTestId("map-spacecraft").getAttribute("x");
  await expect(map).toContainText(/time of flight 275 d/);
  await expect(map).toContainText(/C3 14 km²\/s²/);
  await expect(map).toContainText(/illustrative geometry, not to scale/i);
  expect(await page.getByTestId("map-phase-marker").count()).toBeGreaterThanOrEqual(2);
  await page.goto(`/control/${runId}?day=250`);
  await expect(page.getByTestId("mission-map-text")).toContainText(/91% of the 275-day flight/);
  expect(await page.getByTestId("map-spacecraft").getAttribute("x")).not.toBe(early);
});

test("Earth observation map shows an orbit, not a transfer", async ({ page }) => {
  const runId = await launch(page, "earth-observation", false);
  await page.goto(`/control/${runId}?day=20`);
  await expect(page.getByTestId("mission-map-text")).toContainText(/in low Earth orbit, day 20 of 365/i);
  await expect(page.getByTestId("map-phase-marker")).toHaveCount(0);
});

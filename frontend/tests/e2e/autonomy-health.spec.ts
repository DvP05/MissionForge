import { expect, test, type Page } from "@playwright/test";

/** Phase 6 joined to mission control: blackout autonomy (AC-19) and health monitor (AC-21). */

async function launchFeasible(page: Page): Promise<string> {
  await page.goto("/");
  await page.getByTestId("scenario-card-neo-rendezvous").getByRole("button", { name: /start mission/i }).click();
  await page.waitForURL(/\/mission\/mission-[0-9a-f]{12}$/);
  const id = new URL(page.url()).pathname.split("/").pop() as string;
  await page.goto(`/architect/${id}`);
  await expect(page.getByTestId("analysis-revision")).toContainText(/revision 0/i, { timeout: 30_000 });
  await page.getByTestId("category-nav-communications").click();
  await page.getByTestId("select-comms-xband-medium").click();
  await expect(page.getByTestId("mission-ready-badge")).toHaveText(/^mission-ready$/i);
  await page.getByTestId("launch-button").click();
  await page.waitForURL(/\/control\/[^/]+/, { timeout: 30_000 });
  await expect(page.getByTestId("mission-control")).toBeVisible();
  return new URL(page.url()).pathname.split("/").pop() as string;
}

const API = "http://127.0.0.1:8000";

/** Makes both NEO scenario decisions through the API (what the decision card posts). */
async function decideAll(page: Page, runId: string): Promise<string> {
  let id = runId;
  for (const [eventId, choiceId] of [
    ["scenario-target-illumination", "keep-schedule"],
    ["scenario-solar-event", "continue"],
  ]) {
    const res = await page.request.post(`${API}/api/mission/run/${id}/decision`, { data: { eventId, choiceId } });
    expect(res.ok()).toBe(true);
    id = (await res.json()).data.run.runId as string;
  }
  return id;
}

test.describe("command authority", () => {
  test("blackout shows ONBOARD AUTONOMY with a countdown; a pass shows GROUND CONTROL", async ({ page }) => {
    const runId = await decideAll(page, await launchFeasible(page));
    // Day 295 lies between the day-294 and day-297 passes (8 h each): blackout.
    await page.goto(`/control/${runId}?day=295`);
    const banner = page.getByTestId("authority-banner");
    await expect(banner).toHaveAttribute("data-mode", "onboard");
    await expect(banner).toContainText("ONBOARD AUTONOMY");
    await expect(page.getByTestId("authority-countdown")).toContainText(/next contact in 2 d/i);
    // Day 300.1 is inside the day-300 pass.
    await page.goto(`/control/${runId}?day=300.1`);
    await expect(page.getByTestId("authority-banner")).toHaveAttribute("data-mode", "ground");
    await expect(page.getByTestId("authority-banner")).toContainText("GROUND CONTROL");
  });

  test("the autonomy log shows belief, candidate utilities, selection and reason", async ({ page }) => {
    const runId = await decideAll(page, await launchFeasible(page));
    await page.goto(`/control/${runId}?day=330`);
    const log = page.getByTestId("autonomy-log");
    const entries = log.getByTestId("autonomy-entry");
    await expect(entries).toHaveCount(4);
    await expect(log.locator("[data-maker='onboard-policy']")).toHaveCount(3);
    await expect(log.locator("[data-maker='ground']")).toHaveCount(1);
    const first = entries.first();
    await expect(first).toContainText(/onboard autonomy/i);
    await expect(first.getByRole("list", { name: "Input belief" })).toBeVisible();
    await expect(first.locator("table")).toContainText(/observe:0:/);
    await expect(first).toContainText(/blackout selects/i);
  });

  test("a blackout decision card explains the stored contingency response", async ({ page }) => {
    await launchFeasible(page);
    await page.getByTestId("playback-play").click();
    await expect(page.getByTestId("decision-card")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("decision-authority")).toContainText(/stored contingency responses/i);
  });
});

test.describe("health monitor", () => {
  test("mission control shows raw vs nominal, EWMA and explained findings", async ({ page }) => {
    const runId = await launchFeasible(page);
    await page.goto(`/control/${runId}?day=420`);
    const health = page.getByTestId("health-monitor");
    await expect(health.getByTestId("health-channel-battery_soc")).toBeVisible({ timeout: 30_000 });
    await expect(health).toContainText(/nominal model/i);
    await expect(health.getByTestId("health-channel-battery_soc")).toContainText(/warn .* crit/i);
  });

  test("the review lists autonomy decisions and the health monitor", async ({ page }) => {
    const runId = await launchFeasible(page);
    await page.goto(`/review/${runId}`);
    await expect(page.getByTestId("review-autonomy")).toContainText(/taken on board during communication blackouts/i);
    await expect(page.getByTestId("review-autonomy").getByTestId("autonomy-entry")).toHaveCount(4);
    await expect(page.getByTestId("review-health").getByTestId("health-monitor")).toBeVisible();
    await expect(
      page.getByTestId("review-health").getByTestId(/^health-(finding|none)$/).first(),
    ).toBeVisible({ timeout: 30_000 });
  });
});

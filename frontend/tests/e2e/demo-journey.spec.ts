import { expect, test, type Page } from "@playwright/test";

/**
 * Task 7.5 release QA: the README section 14 / prod section 14 demo route, end to end, at desktop
 * width and at 375 px. (Step 1, the live JPL target, belongs to Phase 5 and is not covered here.)
 */

async function noHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}

for (const width of [1280, 375]) {
  test(`demo route at ${width} px: brief -> repair -> fly -> decide -> review -> export`, async ({ page }) => {
    test.setTimeout(180_000);
    await page.setViewportSize({ width, height: 900 });

    // 2. science objective -> measurement requirements
    await page.goto("/");
    await page.getByTestId("scenario-card-neo-rendezvous").getByRole("button", { name: /start mission/i }).click();
    await page.waitForURL(/\/mission\/mission-[0-9a-f]{12}$/);
    const missionId = new URL(page.url()).pathname.split("/").pop() as string;
    await expect(page.getByTestId("traceability-table")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("trace-row-meas-vnir-spectra")).toBeVisible();
    await noHorizontalOverflow(page);

    // 3-5. coupled budgets; a failing link; repair with a better radio; explained result
    await page.goto(`/architect/${missionId}`);
    await expect(page.getByTestId("analysis-revision")).toContainText(/revision 0/i, { timeout: 30_000 });
    await expect(page.getByTestId("constraint-card-link-margin")).toHaveAttribute("data-status", "fail");
    await expect(page.getByTestId("mission-ready-badge")).toHaveText(/not mission-ready/i);
    const massBefore = await page.getByTestId("budget-tile-mass").innerText();
    await page.getByTestId("category-nav-communications").click();
    await page.getByTestId("select-comms-xband-medium").click();
    await expect(page.getByTestId("analysis-revision")).toContainText(/revision 1/i);
    await expect(page.getByTestId("constraint-card-link-margin")).toHaveAttribute("data-status", "pass");
    await expect(page.getByTestId("mission-ready-badge")).toHaveText(/^mission-ready$/i);
    expect(await page.getByTestId("budget-tile-mass").innerText()).not.toBe(massBefore); // coupled cost
    await noHorizontalOverflow(page);

    // 6-7. launch, telemetry, a seeded decision with a recovery choice
    await page.getByTestId("launch-button").click();
    await page.waitForURL(/\/control\/[^/]+/, { timeout: 30_000 });
    await expect(page.getByTestId("authority-banner")).toBeVisible();
    await page.getByTestId("playback-play").click();
    const card = page.getByTestId("decision-card");
    await expect(card).toBeVisible({ timeout: 60_000 });
    await card.locator("input[type=radio]").first().check();
    await page.getByTestId("confirm-decision").click();
    await page.waitForURL(/\/control\/[^/?]+\?day=/, { timeout: 30_000 });
    await noHorizontalOverflow(page);

    // 8. review: collected vs returned, margins, score, counterfactual
    await page.getByTestId("skip-to-end").click();
    const yes = page.getByTestId("skip-end-confirm-yes");
    if (await yes.isVisible().catch(() => false)) await yes.click();
    await page.getByTestId("open-review").click();
    await page.waitForURL(/\/review\/[^/]+/);
    await expect(page.getByTestId("review-science")).toContainText(/returned/i);
    await expect(page.getByTestId("review-margins")).toBeVisible();
    await expect(page.getByTestId("review-score")).toContainText(/of 100/);
    await expect(page.getByTestId("run-analyst").getByTestId(/^run-analyst-(rec-|none)/).first()).toBeVisible({
      timeout: 30_000,
    });
    await noHorizontalOverflow(page);

    // 9. export the mission dossier
    const downloads: string[] = [];
    page.on("download", (d) => downloads.push(d.suggestedFilename()));
    await page.getByTestId("export-passport").click();
    await expect(page.getByTestId("export-passport-done")).toContainText(/evidence records/i, { timeout: 30_000 });
    await expect.poll(() => downloads.length).toBe(2);
  });
}

test("the saved demo mission loads with no live data and replays identically", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("load-demo").click();
  await page.waitForURL(/\/mission\/mission-demo00000001$/, { timeout: 30_000 });
  await expect(page.getByTestId("workspace-title")).toContainText(/saved demo/i);
  const res = await page.request.get("http://127.0.0.1:8000/api/demo/package");
  const pkg = (await res.json()).data;
  const replay = await page.request.post("http://127.0.0.1:8000/api/mission/replay", { data: { run: pkg.runs[0] } });
  expect((await replay.json()).data.identical).toBe(true);
});

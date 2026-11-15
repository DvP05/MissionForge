import { expect, test, type Page } from "@playwright/test";

/**
 * design_update.md section 17: component selection journey, constraint recovery, mission
 * progression and the honesty checks. Every value asserted comes from the backend analysis.
 */

async function openArchitect(page: Page): Promise<string> {
  await page.goto("/");
  await page.getByTestId("scenario-card-neo-rendezvous").getByRole("button", { name: /start mission/i }).click();
  await page.waitForURL(/\/mission\/mission-[0-9a-f]{12}$/);
  const id = new URL(page.url()).pathname.split("/").pop() as string;
  await page.goto(`/architect/${id}`);
  await expect(page.getByTestId("analysis-revision")).toContainText(/revision 0/i, { timeout: 30_000 });
  return id;
}

const saved = (page: Page, id: string) =>
  page.evaluate((key) => JSON.parse(localStorage.getItem(key) as string), `missionforge:mission:${id}`);

test("component selection journey: add, replace, remove, undo, nothing else changes", async ({ page }) => {
  const id = await openArchitect(page);
  const start = (await saved(page, id)).architecture;

  // 1-2: what is installed
  await page.getByTestId("panel-tab-installed").click();
  await expect(page.getByTestId("installed-inst-hires-camera")).toBeVisible();
  await expect(page.getByTestId("installed-comms-xband-lowgain")).toBeVisible();

  // 3-4: browse an available instrument and inspect units / fidelity
  await page.getByTestId("category-nav-instrument").click();
  const card = page.getByTestId("option-inst-thermal-ir");
  await expect(card).toHaveAttribute("data-state", /available|incompatible/);
  await page.getByTestId("inspect-inst-thermal-ir").click();
  await expect(page.getByTestId("inspector-specs")).toContainText(/kg|W|bit\/s/);
  await page.getByTestId("inspector-view-engineering").click();
  await expect(page.getByTestId("component-inspector")).toContainText(/source/i);

  // 5-9: add it; the revision moves, the part appears, analysis follows
  await page.getByTestId("category-nav-instrument").click();
  await page.getByTestId("select-inst-thermal-ir").click();
  const ask = page.getByTestId("confirm-change");
  await ask.waitFor({ state: "visible", timeout: 1500 }).then(() => ask.click(), () => undefined);
  await expect(page.getByTestId("revision-pill")).toHaveText("Revision 1");
  await expect(page.getByTestId("part-inst-thermal-ir")).toBeVisible();
  await expect(page.getByTestId("option-inst-thermal-ir")).toHaveAttribute("data-state", "installed");
  await expect(page.getByTestId("impact-report")).toContainText(/component installed/i);
  // 10: the impact report shows the engine's before/after values once revision 1 is analysed
  await expect(page.getByTestId("impact-budgets")).toContainText(/kg|W/, { timeout: 30_000 });

  // 11-12: replace the radio: old vs new are compared before anything changes
  await page.getByTestId("category-nav-communications").click();
  await page.getByTestId("select-comms-xband-medium").click();
  const compare = page.getByTestId("change-compare");
  await expect(compare).toContainText(/low-gain/i);
  await expect(compare).toContainText(/medium/i);
  expect((await saved(page, id)).architecture.communicationsId).toBe("comms-xband-lowgain");
  await page.getByTestId("confirm-change").click();
  await expect(page.getByTestId("revision-pill")).toHaveText("Revision 2");
  await expect(page.getByTestId("part-comms-xband-medium")).toBeVisible();
  await expect(page.getByTestId("part-comms-xband-lowgain")).toHaveCount(0);
  await expect(page.getByTestId("impact-constraints")).toContainText(/link margin/i, { timeout: 30_000 });

  // 13-14: remove the added instrument through an explicit, confirmed Remove
  await page.getByTestId("category-nav-instrument").click();
  await page.getByTestId("select-inst-thermal-ir").click();
  await expect(page.getByTestId("change-dialog")).toHaveAttribute("data-kind", "remove");
  await page.getByTestId("confirm-change").click();
  await expect(page.getByTestId("revision-pill")).toHaveText("Revision 3");
  await expect(page.getByTestId("part-inst-thermal-ir")).toHaveCount(0);

  // undo restores the earlier design as a NEW revision (never a visual-only rollback)
  await page.getByTestId("undo-change").click();
  await expect(page.getByTestId("revision-pill")).toHaveText("Revision 4");
  expect((await saved(page, id)).architecture.instrumentIds).toContain("inst-thermal-ir");

  // 15: nothing unrelated changed along the way
  const end = (await saved(page, id)).architecture;
  for (const f of ["launchVehicleId", "busId", "propulsionId", "powerId", "adcsId", "thermalId", "cdhId", "groundSegmentId"]) {
    expect(end[f]).toBe(start[f]);
  }
});

test("constraint recovery: a failing gate opens its subsystem and clears after the repair", async ({ page }) => {
  await openArchitect(page);
  const gate = page.getByTestId("gate-comms");
  await expect(gate).toHaveAttribute("data-status", "FAIL");
  await expect(gate).toContainText(/actual/i);
  await expect(gate).toContainText(/limit/i);
  await expect(page.getByTestId("readiness-summary")).toContainText(/failing/i);
  await page.getByTestId("gate-repair-comms").click();
  await expect(page.getByTestId("options-panel")).toContainText(/communications/i);
  await page.getByTestId("select-comms-xband-medium").click();
  await page.getByTestId("confirm-change").click();
  await expect(page.getByTestId("analysis-revision")).toContainText(/revision 1/i, { timeout: 30_000 });
  await expect(gate).toHaveAttribute("data-status", "PASS");
  // a high score never hides a hard failure: the gates reflect the constraint results only
  await expect(page.getByTestId("gate-thermal")).toHaveAttribute("data-status", "NOT MODELLED");
});

test("progression: stages, next step and a milestone come from real state", async ({ page }) => {
  const id = await openArchitect(page);
  await expect(page.getByTestId("milestone-count")).toContainText("/8");
  await expect(page.getByTestId("next-action")).toContainText(/engineering gates/i);
  await page.getByTestId("category-nav-communications").click();
  await page.getByTestId("select-comms-xband-medium").click();
  await page.getByTestId("confirm-change").click();
  await expect(page.getByTestId("analysis-revision")).toContainText(/revision 1/i, { timeout: 30_000 });
  // the repair earns a real milestone (downlink constraints all pass in the engine)
  await expect(page.getByTestId("badge-toast")).toContainText(/downlink plan ready/i);
  await expect(page.getByTestId("next-action")).not.toContainText(/engineering gates/i);
  // trade study stage is not complete until a trade study is actually run
  await page.getByTestId("mission-progress").getByText(/milestones, badges/i).click();
  await expect(page.getByTestId("milestone-trade")).not.toHaveAttribute("data-status", "complete");
  // flying records the run; the stage rail then opens mission control
  await page.getByTestId("launch-button").click();
  await page.waitForURL(/\/control\//, { timeout: 60_000 });
  await expect(page.getByTestId("stage-nav")).toBeVisible();
  await page.goto(`/architect/${id}`);
  await page.getByTestId("mission-progress").getByText(/milestones, badges/i).click();
  await expect(page.getByTestId("milestone-fly")).toHaveAttribute("data-status", "complete");
});

test("reduced motion setting keeps every action working", async ({ page }) => {
  await openArchitect(page);
  await page.getByTestId("motion-toggle").click();
  await expect(page.locator("html")).toHaveAttribute("data-motion", "reduced");
  await page.getByTestId("category-nav-communications").click();
  await page.getByTestId("select-comms-xband-medium").click();
  await page.getByTestId("confirm-change").click();
  await expect(page.getByTestId("revision-pill")).toHaveText("Revision 1");
  await page.getByTestId("motion-toggle").click();
  await expect(page.locator("html")).toHaveAttribute("data-motion", "system");
});

test("phone width: Build / Spacecraft / Budgets tabs keep every zone reachable", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await openArchitect(page);
  await expect(page.getByTestId("category-nav-power")).toBeVisible();
  await page.getByTestId("mobile-tab-spacecraft").click();
  await expect(page.getByTestId("spacecraft-stage")).toBeVisible();
  await expect(page.getByTestId("readiness-board")).toBeVisible();
  await page.getByTestId("mobile-tab-budgets").click();
  await expect(page.getByTestId("engineering-dashboard")).toBeVisible();
  await expect(page.getByTestId("budget-rail")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

import { createHash } from "node:crypto";

import { expect, test, type Page } from "@playwright/test";

const NEO = "scenario-card-neo-rendezvous";

async function startNeo(page: Page): Promise<string> {
  await page.goto("/");
  await page.getByTestId(NEO).getByRole("button", { name: /start mission/i }).click();
  await page.waitForURL(/\/mission\/mission-[0-9a-f]{12}$/);
  return new URL(page.url()).pathname.split("/").pop() as string;
}

async function openArchitect(page: Page): Promise<string> {
  const id = await startNeo(page);
  await page.goto(`/architect/${id}`);
  await expect(page.getByTestId("analysis-revision")).toContainText(/revision 0/i, { timeout: 30_000 });
  return id;
}

/** Fixes the link-margin failure of the starter design, then launches. */
async function launchFeasible(page: Page): Promise<string> {
  await openArchitect(page);
  await page.getByTestId("category-nav-communications").click();
  await page.getByTestId("select-comms-xband-medium").click();
  await expect(page.getByTestId("analysis-revision")).toContainText(/revision 1/i);
  await expect(page.getByTestId("mission-ready-badge")).toHaveText(/^mission-ready$/i);
  await page.getByTestId("launch-button").click();
  await page.waitForURL(/\/control\/[^/]+/, { timeout: 30_000 });
  await expect(page.getByTestId("mission-control")).toBeVisible();
  return new URL(page.url()).pathname.split("/").pop() as string;
}

async function playUntilDecision(page: Page) {
  await page.getByTestId("playback-play").click();
  await expect(page.getByTestId("decision-card")).toBeVisible({ timeout: 60_000 });
}

test.describe("launch", () => {
  test("a blocked design explains the failing constraint and offers experimental mode", async ({ page }) => {
    await openArchitect(page);
    await page.getByTestId("launch-button").click();
    const blocked = page.getByTestId("launch-blocked");
    await expect(blocked).toBeVisible();
    await expect(blocked.getByTestId("launch-blocked-constraint-link-margin")).toBeVisible();
    await blocked.getByTestId("launch-experimental").click();
    await page.waitForURL(/\/control\/[^/]+/, { timeout: 30_000 });
    await expect(page.getByTestId("experimental-badge")).toContainText(/experimental run/i);
    await expect(page.getByTestId("experimental-badge")).toContainText(/violates hard limits/i);
  });

  test("a feasible design launches and reload of the control URL restores the run", async ({ page }) => {
    const runId = await launchFeasible(page);
    await expect(page.getByTestId("experimental-badge")).toHaveCount(0);
    await page.evaluate(() => window.localStorage.clear());
    await page.reload(); // cache gone: falls back to GET /api/mission/run/{runId}
    await expect(page.getByTestId("mission-control")).toBeVisible();
    await page.goto("/control/run-does-not-exist");
    await expect(page.getByTestId("not-found-state")).toBeVisible();
    expect(runId).toBeTruthy();
  });
});

test.describe("mission control", () => {
  test("phase ribbon shows at least six phases, elapsed day and mode", async ({ page }) => {
    await launchFeasible(page);
    const ribbon = page.getByTestId("phase-ribbon");
    expect(await ribbon.locator("[data-testid^='phase-']").count()).toBeGreaterThanOrEqual(6);
    await expect(page.getByTestId("elapsed-day")).toContainText(/day 0/i);
    await expect(page.getByTestId("spacecraft-mode")).toBeVisible();
    await page.getByTestId("skip-to-end").click();
    await expect(page.getByTestId("elapsed-day")).toContainText(/day 420/i);
    await expect(page.getByTestId("phase-complete")).toHaveAttribute("data-state", "current");
  });

  test("event items show id, mission day, severity text and why; log is filterable", async ({ page }) => {
    await launchFeasible(page);
    await page.getByTestId("skip-to-end").click();
    const item = page.getByTestId("event-item-scenario-target-illumination");
    await expect(item).toContainText("scenario-target-illumination");
    await expect(item.getByTestId("event-day")).toContainText(/day 258/i);
    await expect(item.getByTestId("event-severity")).toHaveText(/info/i);
    await expect(item.getByTestId("event-why")).toContainText(/why this happened/i);
    await page.getByTestId("filter-type").selectOption("decision");
    await expect(page.getByTestId("event-item-scenario-target-illumination")).toBeVisible();
    await expect(page.getByTestId("event-item-commissioning-milestone-1")).toHaveCount(0);
    await page.getByTestId("filter-type").selectOption("all");
    await page.getByTestId("filter-severity").selectOption("warning");
    await expect(page.getByTestId("event-item-scenario-solar-event")).toBeVisible();
    await expect(page.getByTestId("event-item-scenario-target-illumination")).toHaveCount(0);
  });

  test("telemetry cards and charts share a mission-day axis and show units and fidelity", async ({ page }) => {
    await launchFeasible(page);
    await page.getByTestId("skip-to-end").click();
    for (const ch of ["battery_soc", "propellant_fraction", "buffer_fill", "link_margin_db", "pointing_error_deg"]) {
      const card = page.getByTestId(`telemetry-card-${ch}`);
      await expect(card).toBeVisible();
      await expect(card.locator("[data-testid^='fidelity-badge-']").first()).toBeVisible();
      const chart = page.getByTestId(`telemetry-chart-${ch}`);
      await expect(chart).toHaveAttribute("data-x-axis", "mission-day");
      await expect(chart).toHaveAttribute("data-x-domain", /^0,420$/);
      await expect(chart.getByTestId("chart-unit")).toHaveText(/\S/);
      await expect(chart.locator(".recharts-wrapper")).toBeVisible();
    }
    await expect(page.getByTestId("telemetry-card-link_margin_db")).toContainText("dB");
    await expect(page.getByTestId("telemetry-chart-link_margin_db")).toContainText(/mission day \(d\)/i);
  });

  test("2D schematic is labelled illustrative and works without WebGL", async ({ page }) => {
    await page.addInitScript(() => {
      const orig = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function (this: HTMLCanvasElement, type: string, ...rest: unknown[]) {
        if (/webgl/i.test(type)) return null;
        return (orig as (...a: unknown[]) => unknown).call(this, type, ...rest) as never;
      } as typeof orig;
    });
    await launchFeasible(page);
    await expect(page.getByTestId("schematic-2d")).toContainText(/illustrative/i);
    await playUntilDecision(page);
    await expect(page.getByTestId("schematic-2d")).toBeVisible();
  });

  test("375 px has no horizontal overflow on control and review", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    const runId = await launchFeasible(page);
    for (const path of [`/control/${runId}`, `/review/${runId}`]) {
      await page.goto(path);
      await expect(page.locator("h1").first()).toBeVisible();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow).toBeLessThanOrEqual(0);
    }
  });
});

test.describe("decisions", () => {
  test("playback pauses at a decision; the choice is required, keyboard operable, and lands in log and review", async ({
    page,
  }) => {
    await launchFeasible(page);
    await playUntilDecision(page);
    const card = page.getByTestId("decision-card");
    await expect(card).toContainText(/illumination/i);
    await expect(card).toContainText(/scenario uncertainty/i);
    expect(await card.locator("[data-testid^='choice-']").count()).toBeGreaterThanOrEqual(2);
    await expect(card.getByTestId("choice-extend-observations").or(card.getByTestId("choice-keep-schedule")).first()).toContainText(/\S/);
    await expect(card.getByTestId("decision-situation")).toBeVisible();
    // A choice is required: confirm is disabled and play is blocked.
    await expect(card.getByTestId("confirm-decision")).toBeDisabled();
    await expect(page.getByTestId("playback-play")).toBeDisabled();
    // Keyboard only: focus the first radio, arrow to the next, confirm with Enter/Space.
    const first = card.getByRole("radio").first();
    await first.focus();
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Tab");
    await expect(card.getByTestId("confirm-decision")).toBeFocused();
    const chosenLabel = (await card.locator("input[type=radio]:checked + *, [role=radio][aria-checked=true]").first().innerText()).trim();
    expect(chosenLabel.length).toBeGreaterThan(0);
    await page.keyboard.press("Enter");
    await page.waitForURL(/\/control\/[^/?]+\?day=258/, { timeout: 30_000 });
    await expect(page.getByTestId("elapsed-day")).toContainText(/day 258/i);
    await expect(page.getByTestId("decision-card")).toHaveCount(0);
    const item = page.getByTestId("event-item-scenario-target-illumination");
    await expect(item.getByTestId("decision-maker")).toContainText(/player/i);
    const newRun = new URL(page.url()).pathname.split("/").pop() as string;
    await page.getByTestId("skip-to-end").click();
    await page.getByTestId("open-review").click();
    await page.waitForURL(new RegExp(`/review/${newRun}`));
    await expect(page.getByTestId("review-decisions")).toContainText(/illumination/i);
    await expect(page.getByTestId("review-decisions")).toContainText(/player/i);
  });

  test("0.5x, 1x and 4x playback give identical review text", async ({ page }) => {
    test.setTimeout(240_000);
    await launchFeasible(page);
    const controlUrl = page.url();
    const hashes: string[] = [];
    for (const speed of ["0.5", "1", "4"]) {
      await page.goto(controlUrl);
      await expect(page.getByTestId("mission-control")).toBeVisible();
      await page.getByTestId(`speed-${speed}`).click();
      await expect(page.getByTestId(`speed-${speed}`)).toHaveAttribute("aria-pressed", "true");
      await page.getByTestId("playback-play").click();
      await expect(page.getByTestId("decision-card")).toBeVisible({ timeout: 90_000 });
      await page.getByTestId("skip-to-end").click();
      await page.getByTestId("open-review").click();
      await page.waitForURL(/\/review\//);
      await expect(page.getByTestId("review-outcome")).toBeVisible();
      const text = await page.getByTestId("review-page").innerText();
      hashes.push(createHash("sha256").update(text).digest("hex"));
    }
    expect(hashes[1]).toBe(hashes[0]);
    expect(hashes[2]).toBe(hashes[0]);
  });

  test("skip to next decision stops at the card", async ({ page }) => {
    await launchFeasible(page);
    await page.getByTestId("skip-next-decision").click();
    await expect(page.getByTestId("decision-card")).toBeVisible();
    await expect(page.getByTestId("elapsed-day")).toContainText(/day 258/i);
  });
});

test.describe("review", () => {
  test("shows the section structure with honest provenance", async ({ page }) => {
    const runId = await launchFeasible(page);
    await page.goto(`/review/${runId}`);
    await expect(page.getByTestId("review-outcome")).toContainText(/partial|success|failure|terminated/i);
    await expect(page.getByTestId("review-outcome")).toContainText(/objectives achieved/i);
    const objectives = page.getByTestId("review-objectives");
    await expect(objectives.getByTestId("objective-status-obj-morphology")).toHaveText(/achieved/i);
    await expect(objectives.getByTestId("objective-status-obj-composition")).toHaveText(/partial/i);
    await expect(page.getByTestId("review-science")).toContainText(/collected/i);
    await expect(page.getByTestId("review-science")).toContainText(/returned/i);
    await expect(page.getByTestId("review-margins")).toContainText(/design-time/i);
    await expect(page.getByTestId("review-margins").locator(".recharts-wrapper")).toBeVisible();
    await expect(page.getByTestId("review-timeline")).toContainText(/scenario-target-illumination/);
    expect(await page.getByTestId("review-root-causes").locator("li").count()).toBeGreaterThanOrEqual(1);
    await expect(page.getByTestId("review-root-causes").locator("li").first()).toContainText(/1/);
    expect(await page.getByTestId("review-counterfactuals").locator("li").count()).toBeGreaterThanOrEqual(1);
    await expect(page.getByTestId("review-limitations")).toContainText(/not orbital propagation/i);
    const dims = page.getByTestId("review-score").locator("[data-testid^='score-dimension-']");
    expect(await dims.count()).toBe(5);
    await expect(page.getByTestId("score-dimension-scientific-return")).toContainText(/30/);
    await expect(page.getByTestId("score-dimension-operations-quality")).toContainText(/10/);
  });

  test("an empty counterfactual list says none was computed", async ({ page }) => {
    const runId = await launchFeasible(page);
    await page.route(`**/api/mission/run/${runId}`, async (route) => {
      const res = await route.fetch();
      const body = await res.json();
      body.data.run.finalReport.counterfactuals = [];
      body.data.finalReport.counterfactuals = [];
      await route.fulfill({ response: res, json: body });
    });
    await page.evaluate(() => window.localStorage.clear());
    await page.goto(`/review/${runId}`);
    await expect(page.getByTestId("review-counterfactuals")).toContainText(/no counterfactual computed/i);
  });

  test("an experimental run is badged on the review", async ({ page }) => {
    await openArchitect(page);
    await page.getByTestId("launch-button").click();
    await page.getByTestId("launch-experimental").click();
    await page.waitForURL(/\/control\/[^/]+/, { timeout: 30_000 });
    const runId = new URL(page.url()).pathname.split("/").pop() as string;
    await page.goto(`/review/${runId}`);
    await expect(page.getByTestId("experimental-badge")).toContainText(/violates hard limits/i);
  });

  test("unknown run shows not found", async ({ page }) => {
    await page.goto("/review/run-does-not-exist");
    await expect(page.getByTestId("not-found-state")).toBeVisible();
  });
});

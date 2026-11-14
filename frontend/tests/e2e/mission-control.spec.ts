import { readFileSync } from "node:fs";
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

/** Skip to end; confirms the ground-defaults dialog when decisions are still ahead. */
async function skipToEnd(page: Page) {
  await page.getByTestId("skip-to-end").click();
  const yes = page.getByTestId("skip-end-confirm-yes");
  if (await yes.isVisible().catch(() => false)) await yes.click();
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
    await skipToEnd(page);
    await expect(page.getByTestId("elapsed-day")).toContainText(/day 420/i);
    await expect(page.getByTestId("phase-complete")).toHaveAttribute("data-state", "current");
  });

  test("event items show id, mission day, severity text and why; log is filterable", async ({ page }) => {
    await launchFeasible(page);
    await skipToEnd(page);
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
    await skipToEnd(page);
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
  test("keyboard only: play, card takes focus, choose, confirm; the chosen option reaches the POST, log and review", async ({
    page,
  }) => {
    await launchFeasible(page);
    // Reach Play with Tab only, then start playback with Enter.
    for (let i = 0; i < 40; i += 1) {
      await page.keyboard.press("Tab");
      if ((await page.evaluate(() => document.activeElement?.getAttribute("data-testid"))) === "playback-play") break;
    }
    await expect(page.getByTestId("playback-play")).toBeFocused();
    await page.keyboard.press("Enter");
    const card = page.getByTestId("decision-card");
    await expect(card).toBeVisible({ timeout: 60_000 });
    await expect(card).toContainText(/illumination/i);
    await expect(card).toContainText(/scenario uncertainty/i);
    expect(await card.locator("[data-testid^='choice-']").count()).toBeGreaterThanOrEqual(2);
    await expect(card.getByTestId("decision-situation")).toBeVisible();
    await expect(card.getByRole("alert")).toContainText(/decision required/i);
    // Focus moved to the card heading when it appeared.
    await expect(card.getByRole("heading", { level: 2 })).toBeFocused();
    await expect(card.getByTestId("confirm-decision")).toBeDisabled();
    await expect(page.getByTestId("playback-play")).toBeDisabled();
    await expect(page.getByTestId("skip-to-end")).toBeDisabled();
    // Tab into the radio group, move to the second option, Tab to Confirm.
    await page.keyboard.press("Tab");
    await expect(card.getByRole("radio").first()).toBeFocused();
    await page.keyboard.press("ArrowDown");
    const choiceId = await card.locator("input[type=radio]:checked").getAttribute("value");
    const choiceLabel = (await card.locator("label:has(input:checked) span.font-medium").innerText()).trim();
    expect(choiceId).toBeTruthy();
    await page.keyboard.press("Tab");
    await expect(card.getByTestId("confirm-decision")).toBeFocused();
    const request = page.waitForRequest((r) => r.url().includes("/decision") && r.method() === "POST");
    await page.keyboard.press("Enter");
    expect((await request).postDataJSON()).toEqual({ eventId: "scenario-target-illumination", choiceId });
    await page.waitForURL(/\/control\/[^/?]+\?day=258/, { timeout: 30_000 });
    await expect(page.getByTestId("elapsed-day")).toContainText(/day 258/i);
    await expect(page.getByTestId("decision-card")).toHaveCount(0);
    const item = page.getByTestId("event-item-scenario-target-illumination");
    await expect(item.getByTestId("decision-maker")).toContainText(choiceLabel);
    await expect(item.getByTestId("decision-maker")).toContainText(/player/i);
  });

  test("skip to end is disabled while a decision is pending", async ({ page }) => {
    await launchFeasible(page);
    await page.getByTestId("skip-next-decision").click();
    await expect(page.getByTestId("decision-card")).toBeVisible();
    await expect(page.getByTestId("skip-to-end")).toBeDisabled();
  });

  test("skip to end asks first and states how many decisions use ground defaults", async ({ page }) => {
    await launchFeasible(page);
    await page.getByTestId("skip-to-end").click();
    const dialog = page.getByTestId("skip-end-confirm");
    await expect(dialog).toContainText("2 undecided decisions will use ground defaults");
    await page.getByTestId("skip-end-cancel").click();
    await expect(dialog).toHaveCount(0);
    await expect(page.getByTestId("elapsed-day")).toContainText(/day 0/i);
    await page.getByTestId("skip-to-end").click();
    await page.getByTestId("skip-end-confirm-yes").click();
    await expect(page.getByTestId("elapsed-day")).toContainText(/day 420/i);
    await expect(page.getByTestId("event-item-scenario-solar-event").getByTestId("decision-maker")).toContainText(/ground/i);
  });

  test("the chosen option lands in the log and the review", async ({ page }) => {
    await launchFeasible(page);
    await playUntilDecision(page);
    const label = (await page.getByTestId("choice-extend-observation").locator("span.font-medium").innerText()).trim();
    await page.getByTestId("choice-extend-observation").click();
    await page.getByTestId("confirm-decision").click();
    await page.waitForURL(/\/control\/[^/?]+\?day=258/, { timeout: 30_000 });
    await expect(page.getByTestId("event-item-scenario-target-illumination").getByTestId("decision-maker")).toContainText(label);
    await page.getByTestId("skip-next-decision").click();
    await page.getByTestId("choice-continue").click();
    await page.getByTestId("confirm-decision").click();
    await page.waitForURL(/\/control\/[^/?]+\?day=302/, { timeout: 30_000 });
    await skipToEnd(page);
    await page.getByTestId("open-review").click();
    await expect(page.getByTestId("review-decisions")).toContainText(label);
    await expect(page.getByTestId("review-decisions")).toContainText(/Continue science/);
    await expect(page.getByTestId("review-decisions")).not.toContainText(/ground/);
  });

  test("0.5x, 1x and 4x playback with the same choices give identical review text", async ({ page }) => {
    test.setTimeout(300_000);
    await launchFeasible(page);
    const controlUrl = page.url();
    const hashes: string[] = [];
    for (const speed of ["0.5", "1", "4"]) {
      await page.goto(controlUrl);
      await expect(page.getByTestId("mission-control")).toBeVisible();
      for (const [choice, day] of [
        ["extend-observation", "258"],
        ["continue", "302"],
      ] as const) {
        await page.getByTestId(`speed-${speed}`).click();
        await expect(page.getByTestId(`speed-${speed}`)).toHaveAttribute("aria-pressed", "true");
        await page.getByTestId("playback-play").click();
        await expect(page.getByTestId("decision-card")).toBeVisible({ timeout: 90_000 });
        await page.getByTestId(`choice-${choice}`).click();
        await page.getByTestId("confirm-decision").click();
        await page.waitForURL(new RegExp(`\\?day=${day}`), { timeout: 30_000 });
      }
      await skipToEnd(page);
      await page.getByTestId("open-review").click();
      await page.waitForURL(/\/review\//);
      await expect(page.getByTestId("review-outcome")).toBeVisible();
      await expect(page.getByTestId("review-decisions")).toContainText(/player/);
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
    await expect(page.getByTestId("review-root-causes").locator("li").first()).toContainText("Rank 1");
    expect(await page.getByTestId("review-counterfactuals").locator("li").count()).toBeGreaterThanOrEqual(1);
    await expect(page.getByTestId("review-limitations")).toContainText(/not orbital propagation/i);
    const dims = page.getByTestId("review-score").locator("[data-testid^='score-dimension-']");
    expect(await dims.count()).toBe(5);
    await expect(page.getByTestId("score-dimension-scientific-return")).toContainText("weight 30");
    await expect(page.getByTestId("score-dimension-mission-execution")).toContainText("weight 25");
    await expect(page.getByTestId("score-dimension-engineering-robustness")).toContainText("weight 20");
    await expect(page.getByTestId("score-dimension-resource-stewardship")).toContainText("weight 15");
    await expect(page.getByTestId("score-dimension-operations-quality")).toContainText("weight 10");
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

test.describe("robustness and design-time limit", () => {
  test("a malformed cached run is discarded and the page recovers via GET", async ({ page }) => {
    const runId = await launchFeasible(page);
    await page.evaluate((id) => {
      window.localStorage.setItem(
        `missionforge:run:${id}`,
        JSON.stringify({ analysis: null, run: { runId: id, events: [], telemetry: [] } }),
      );
    }, runId);
    for (const path of [`/control/${runId}`, `/review/${runId}`]) {
      await page.goto(path);
      await expect(page.getByTestId(path.startsWith("/control") ? "mission-control" : "review-page")).toBeVisible();
    }
  });

  test("a backend run missing required fields shows a recoverable error, not a crash", async ({ page }) => {
    const runId = await launchFeasible(page);
    await page.route(`**/api/mission/run/${runId}`, (route) =>
      route.fulfill({
        json: { ok: true, data: { run: { runId }, analysis: null }, error: null, meta: { requestId: "t", schemaVersion: "1.0" } },
      }),
    );
    await page.evaluate(() => window.localStorage.clear());
    await page.goto(`/review/${runId}`);
    await expect(page.getByTestId("error-state")).toBeVisible();
  });

  test("a ?day= beyond the first undecided decision is clamped to it", async ({ page }) => {
    const runId = await launchFeasible(page);
    await page.goto(`/control/${runId}?day=400`);
    await expect(page.getByTestId("elapsed-day")).toContainText(/day 258/i);
    await expect(page.getByTestId("decision-card")).toBeVisible();
  });

  test("link margin shows the design-time limit with provenance, on card and chart", async ({ page }) => {
    await launchFeasible(page);
    await page.getByTestId("skip-next-decision").click();
    await page.getByTestId("choice-keep-schedule").click();
    await page.getByTestId("confirm-decision").click();
    await page.waitForURL(/\?day=258/);
    await expect(page.getByTestId("telemetry-card-link_margin_db").getByTestId("link-limit")).toContainText(/design-time limit/i);
    const chart = page.getByTestId("telemetry-chart-link_margin_db");
    await expect(chart.getByTestId("link-limit")).toContainText(/design-time limit/i);
    await expect(chart.locator("[data-testid^='fidelity-badge-']").first()).toBeVisible();
    await expect(page.getByTestId("telemetry-chart-battery_soc").getByTestId("link-limit")).toHaveCount(0);
  });

  test("each chart has a data table alternative", async ({ page }) => {
    await launchFeasible(page);
    await skipToEnd(page);
    const data = page.getByTestId("chart-data-link_margin_db");
    await data.locator("summary").click();
    await expect(data.locator("table")).toBeVisible();
    await expect(data.locator("tbody tr").first()).toContainText(/\d/);
  });

  test("the skip-to-end confirmation closes when a decision becomes pending", async ({ page }) => {
    await launchFeasible(page);
    await page.getByTestId("skip-to-end").click();
    await expect(page.getByTestId("skip-end-confirm")).toBeVisible();
    await page.getByTestId("playback-play").click(); // playing reaches the first decision
    await expect(page.getByTestId("decision-card")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("skip-end-confirm")).toHaveCount(0);
  });
});

test.describe("evidence passport", () => {
  test("export downloads the JSON and HTML files", async ({ page }) => {
    const runId = await launchFeasible(page);
    await page.goto(`/review/${runId}`);
    const downloads: import("@playwright/test").Download[] = [];
    page.on("download", (d) => downloads.push(d));
    await page.getByTestId("export-passport").click();
    await expect(page.getByTestId("export-passport-done")).toContainText(/evidence records/i);
    await expect.poll(() => downloads.length).toBe(2);
    const names = downloads.map((d) => d.suggestedFilename()).sort();
    expect(names).toEqual([`missionforge-passport-${runId}.html`, `missionforge-passport-${runId}.json`]);
    const json = downloads.find((d) => d.suggestedFilename().endsWith(".json"))!;
    const html = downloads.find((d) => d.suggestedFilename().endsWith(".html"))!;
    const pkg = JSON.parse(readFileSync((await json.path())!, "utf8"));
    expect(pkg.packageSchemaVersion).toBe("1.0");
    expect(pkg.runs[0].runId).toBe(runId);
    expect(pkg.evidence.length).toBeGreaterThan(10);
    expect(pkg.manifest.engineVersion).toBeTruthy();
    const text = readFileSync((await html.path())!, "utf8");
    expect(text).toContain("not a NASA/JPL product or endorsement");
    expect(text).toContain("Sources and assumptions");
    expect(text).not.toMatch(/<script/i);
  });

  test("the replay line comes from the structured status, not from text in the HTML", async ({ page }) => {
    const runId = await launchFeasible(page);
    await page.goto(`/review/${runId}`);
    await page.route("**/api/mission/dossier", async (route) => {
      const res = await route.fetch();
      const body = await res.json();
      body.data.replayStatus = "diverged";
      body.data.html = body.data.html.replace("</main>", "<p>Probe (identical replay)</p></main>");
      await route.fulfill({ response: res, json: body });
    });
    await page.getByTestId("export-passport").click();
    const done = page.getByTestId("export-passport-done");
    await expect(done).toContainText(/not an identical replay \(diverged\)/);
    await expect(done).not.toContainText(/verified identical/);
  });

  test("a failing export says nothing was downloaded", async ({ page }) => {
    const runId = await launchFeasible(page);
    await page.goto(`/review/${runId}`);
    await page.route("**/api/mission/dossier", (r) => r.abort());
    await page.getByTestId("export-passport").click();
    await expect(page.getByTestId("export-passport-error")).toContainText(/nothing was downloaded/i);
  });
});

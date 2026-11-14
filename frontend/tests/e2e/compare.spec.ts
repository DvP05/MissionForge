import { expect, test, type Page } from "@playwright/test";

const NEO = "scenario-card-neo-rendezvous";
const TRADE = "**/api/mission/trade-study";

async function startNeo(page: Page): Promise<string> {
  await page.goto("/");
  await page.getByTestId(NEO).getByRole("button", { name: /start mission/i }).click();
  await page.waitForURL(/\/mission\/mission-[0-9a-f]{12}$/);
  return new URL(page.url()).pathname.split("/").pop() as string;
}

async function openArena(page: Page): Promise<string> {
  const id = await startNeo(page);
  await page.goto(`/arena/${id}`);
  await expect(page.getByTestId("compare-view")).toBeVisible({ timeout: 30_000 });
  return id;
}

async function stored(page: Page, id: string) {
  return page.evaluate((key) => JSON.parse(window.localStorage.getItem(key) as string), `missionforge:mission:${id}`);
}

/** Adds Alternative A with the medium X-band radio and runs the study; returns the API response body. */
async function runWithMediumRadio(page: Page) {
  await page.getByTestId("add-alternative").click();
  await page.getByTestId("alt-select-A-communications").selectOption("comms-xband-medium");
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.url().includes("/api/mission/trade-study") && r.request().method() === "POST"),
    page.getByTestId("run-trade-study").click(),
  ]);
  return { response, body: await response.json() };
}

test.describe("compare view", () => {
  test("the arena hosts the compare view, explains persistence, and has no alternatives at first", async ({ page }) => {
    await openArena(page);
    await expect(page.getByTestId("compare-view")).toContainText(/not saved/i);
    await expect(page.getByTestId("compare-view")).toContainText(/baseline/i);
    await expect(page.getByTestId("run-trade-study")).toBeDisabled();
    await expect(page.locator('[data-testid^="alternative-card-"]')).toHaveCount(0);
  });

  test("duplicates the baseline as Alternative A, B, C and stops at three", async ({ page }) => {
    await openArena(page);
    for (const label of ["A", "B", "C"]) {
      await page.getByTestId("add-alternative").click();
      await expect(page.getByTestId(`alternative-card-${label}`)).toContainText(`Alternative ${label}`);
    }
    await expect(page.getByTestId("add-alternative")).toBeDisabled();
    await expect(page.getByTestId("compare-view")).toContainText(/up to 3 alternatives/i);
    // a copy starts identical to the baseline
    await expect(page.getByTestId("alt-select-A-communications")).toHaveValue("comms-xband-low");
    await page.getByTestId("remove-alternative-B").click();
    await expect(page.locator('[data-testid^="alternative-card-"]')).toHaveCount(2);
    await expect(page.getByTestId("add-alternative")).toBeEnabled();
  });

  test("a radio swap produces a table with values, deltas from the API, direction icon and text", async ({ page }) => {
    await openArena(page);
    const { response, body } = await runWithMediumRadio(page);
    expect(response.status()).toBe(200);
    const deltas = body.data.alternatives[0].deltas as Record<string, number>;
    const table = page.getByTestId("compare-table");
    await expect(table).toBeVisible();
    await expect(table.getByRole("columnheader", { name: /baseline/i })).toBeVisible();
    await expect(table.getByRole("columnheader", { name: /alternative a/i })).toBeVisible();

    let directional = 0;
    for (const [metric, delta] of Object.entries(deltas)) {
      const cell = page.getByTestId(`delta-${metric}-A`);
      await expect(cell).toBeVisible();
      const direction = Math.abs(delta) < 1e-9 ? "none" : delta > 0 ? "up" : "down";
      await expect(cell).toHaveAttribute("data-direction", direction);
      await expect(cell).toContainText(direction === "up" ? /higher/i : direction === "down" ? /lower/i : /no change/i);
      if (direction !== "none") {
        directional += 1;
        await expect(cell.locator("svg")).toHaveCount(1); // icon, in addition to the text
      }
    }
    expect(directional).toBeGreaterThan(0);
    // wet mass goes up with a heavier radio: the sign shown matches the API
    const wet = deltas["wet_mass_kg"];
    await expect(page.getByTestId("delta-wet_mass_kg-A")).toContainText(wet > 0 ? "higher" : "lower");
    // values come with a fidelity badge
    await expect(page.getByTestId("compare-cell-wet_mass_kg-base").locator('[data-testid^="fidelity-badge-"]')).toHaveCount(1);
  });

  test("feasibility and mission-ready are shown per design", async ({ page }) => {
    await openArena(page);
    await runWithMediumRadio(page);
    await expect(page.getByTestId("compare-feasibility-base")).toContainText(/infeasible/i);
    await expect(page.getByTestId("compare-feasibility-base")).toContainText(/not mission-ready/i);
    await expect(page.getByTestId("compare-feasibility-A")).toContainText(/^\s*feasible/i);
    await expect(page.getByTestId("compare-feasibility-A")).toContainText(/^(?!.*not mission-ready).*mission-ready/is);
  });

  test("the baseline is untouched: stored mission, revision and request body", async ({ page }) => {
    const id = await openArena(page);
    const before = await stored(page, id);
    let requestBody: { baseMissionState: unknown; alternatives: { architecture: { communicationsId: string } }[] } | null = null;
    page.on("request", (r) => {
      if (r.url().includes("/api/mission/trade-study")) requestBody = r.postDataJSON();
    });
    await runWithMediumRadio(page);
    expect(requestBody).not.toBeNull();
    expect(requestBody!.baseMissionState).toEqual(before);
    expect(requestBody!.alternatives[0].architecture.communicationsId).toBe("comms-xband-medium");
    const after = await stored(page, id);
    expect(after).toEqual(before);
    expect(after.architecture.communicationsId).toBe("comms-xband-low");
    await expect(page.getByTestId("revision-pill")).toHaveText("Revision 0");
  });

  test("alternatives are session-only: a reload starts without them", async ({ page }) => {
    await openArena(page);
    await runWithMediumRadio(page);
    await page.reload();
    await expect(page.getByTestId("compare-view")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid^="alternative-card-"]')).toHaveCount(0);
    await expect(page.getByTestId("compare-table")).toHaveCount(0);
  });

  test("editing an alternative after a run marks the table out of date", async ({ page }) => {
    await openArena(page);
    await runWithMediumRadio(page);
    await page.getByTestId("alt-select-A-communications").selectOption("comms-xband-low");
    await expect(page.getByTestId("compare-stale")).toContainText(/out of date/i);
    await page.getByTestId("run-trade-study").click();
    await expect(page.getByTestId("compare-stale")).toHaveCount(0);
  });

  test("instruments are a toggle list in the alternative", async ({ page }) => {
    await openArena(page);
    await page.getByTestId("add-alternative").click();
    const box = page.getByTestId("alt-instrument-A-inst-thermal-ir");
    await expect(box).not.toBeChecked();
    await box.check();
    const [response] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/api/mission/trade-study")),
      page.getByTestId("run-trade-study").click(),
    ]);
    const body = await response.json();
    expect(body.ok).toBe(true);
    expect(body.data.alternatives[0].analysis.budgets.dryMassKg.value).toBeGreaterThan(
      body.data.baseAnalysis.budgets.dryMassKg.value,
    );
  });

  test("a design the API rejects is named by its alternative letter", async ({ page }) => {
    await openArena(page);
    await page.route(TRADE, async (route) => {
      await route.fulfill({
        status: 422,
        json: {
          ok: false,
          data: null,
          error: {
            code: "CATALOG_ITEM_NOT_FOUND",
            message: "The design references catalogue components that do not exist.",
            retryable: false,
            details: { design: { role: "alternative", index: 1 }, items: [{ path: "architecture.communicationsId", id: "x" }] },
          },
          meta: { requestId: "r", schemaVersion: "1.0" },
        },
      });
    });
    await page.getByTestId("add-alternative").click();
    await page.getByTestId("add-alternative").click();
    await page.getByTestId("run-trade-study").click();
    await expect(page.getByTestId("compare-error")).toContainText(/alternative b/i);
    await expect(page.getByTestId("compare-table")).toHaveCount(0);
  });

  test("a metric the API omitted shows a dash and a reason, never 0", async ({ page }) => {
    await openArena(page);
    await page.route(TRADE, async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      delete body.data.alternatives[0].deltas["peak_power_w"];
      await route.fulfill({ response, json: body });
    });
    await runWithMediumRadio(page);
    const cell = page.getByTestId("delta-peak_power_w-A");
    await expect(cell).toHaveAttribute("data-direction", "undefined");
    await expect(cell).toContainText("—");
    await expect(cell).toContainText(/no difference reported/i);
    await expect(cell).not.toContainText(/\b0\b/);
  });

  test("a server failure shows an error and keeps the alternatives", async ({ page }) => {
    await openArena(page);
    await page.route(TRADE, (route) => route.fulfill({ status: 500, json: { ok: false, data: null, error: { code: "INTERNAL_ERROR", message: "boom", retryable: true }, meta: { requestId: "r", schemaVersion: "1.0" } } }));
    await page.getByTestId("add-alternative").click();
    await page.getByTestId("run-trade-study").click();
    await expect(page.getByTestId("compare-error")).toBeVisible();
    await expect(page.getByTestId("alternative-card-A")).toBeVisible();
  });

  test("375 px: no page-level horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await openArena(page);
    await runWithMediumRadio(page);
    await expect(page.getByTestId("compare-table")).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
});

test.describe("Task 3.4 minors", () => {
  test("a failed-shaped analysis shows no derived badge on the feasibility card or constraint margin", async ({ page }) => {
    const id = await startNeo(page);
    await page.route("**/api/mission/validate", async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      const a = body.data.analysis;
      const placeholder = { fidelity: "not-modelled", sourceName: "MISSIONFORGE analysis", assumptions: ["Analysis could not run; placeholder value, not a result."] };
      for (const [k, v] of Object.entries(a.budgets)) {
        a.budgets[k] = v && typeof v === "object" ? { value: 0, unit: (v as { unit: string }).unit, provenance: placeholder } : 0;
      }
      a.science = { ...a.science, coverageScore: 0, collectedFraction: 0, returnedFraction: 0 };
      a.constraints = [
        {
          id: "catalog-item-not-found",
          label: "Catalogue item not found",
          status: "fail",
          severity: 3,
          marginFraction: 0,
          explanation: "Analysis could not run: unknown id.",
          impactedSubsystems: ["architecture"],
          suggestedActions: [],
        },
      ];
      a.feasibility = "infeasible";
      a.missionReady = false;
      await route.fulfill({ response, json: body });
    });
    await page.goto(`/architect/${id}`);
    await expect(page.getByTestId("constraint-card-catalog-item-not-found")).toBeVisible({ timeout: 30_000 });
    const feas = page.getByTestId("budget-tile-feasibility");
    await expect(feas.getByTestId("feasibility-badge")).toBeVisible();
    await expect(feas.locator('[data-testid^="fidelity-badge-"]')).toHaveCount(0);
    const card = page.getByTestId("constraint-card-catalog-item-not-found");
    await expect(card.getByTestId("constraint-margin")).toBeVisible();
    await expect(card.getByTestId("constraint-margin").locator('[data-testid^="fidelity-badge-"]')).toHaveCount(0);
    // every row of an all-missing tile carries its reason
    const mass = page.getByTestId("budget-tile-mass");
    await expect(mass.getByTestId("missing-reason")).toHaveCount(4);
  });
});

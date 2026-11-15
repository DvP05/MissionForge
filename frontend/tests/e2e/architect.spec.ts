import { expect, test, type Page } from "@playwright/test";

const NEO = "scenario-card-neo-rendezvous";
const VALIDATE = "**/api/mission/validate";

async function startNeo(page: Page): Promise<string> {
  await page.goto("/");
  await page.getByTestId(NEO).getByRole("button", { name: /start mission/i }).click();
  await page.waitForURL(/\/mission\/mission-[0-9a-f]{12}$/);
  return new URL(page.url()).pathname.split("/").pop() as string;
}

/** Opens the architect with the first analysis (revision 0) on screen. */
async function openArchitect(page: Page): Promise<string> {
  const id = await startNeo(page);
  await page.goto(`/architect/${id}`);
  await expect(page.getByTestId("analysis-revision")).toContainText(/revision 0/i, { timeout: 30_000 });
  return id;
}

async function stored(page: Page, id: string) {
  return page.evaluate((key) => JSON.parse(window.localStorage.getItem(key) as string), `missionforge:mission:${id}`);
}

async function choose(page: Page, category: string, componentId: string) {
  await page.getByTestId(`category-nav-${category}`).click();
  await page.getByTestId(`select-${componentId}`).click();
  // replacing a single-slot component (or removing an instrument) is confirmed first
  if (category !== "instrument") await page.getByTestId("confirm-change").click();
}

test.describe("architect layout", () => {
  test("desktop columns are about 22 / 48 / 30 and the bottom drawer exists", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await openArchitect(page);
    const box = async (id: string) => (await page.getByTestId(id).boundingBox())!;
    const left = await box("architect-left");
    const center = await box("architect-center");
    const right = await box("architect-right");
    const total = left.width + center.width + right.width;
    expect(left.width / total).toBeGreaterThan(0.19);
    expect(left.width / total).toBeLessThan(0.25);
    expect(center.width / total).toBeGreaterThan(0.44);
    expect(center.width / total).toBeLessThan(0.52);
    expect(right.width / total).toBeGreaterThan(0.27);
    expect(right.width / total).toBeLessThan(0.33);
    expect(Math.abs(left.y - right.y)).toBeLessThan(4);
    const drawer = await box("bottom-drawer");
    expect(drawer.y).toBeGreaterThan(right.y);
  });

  test("375 px stacks the columns with no horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await openArchitect(page);
    const left = (await page.getByTestId("architect-left").boundingBox())!;
    const right = (await page.getByTestId("architect-right").boundingBox())!;
    expect(Math.abs(left.x - right.x)).toBeLessThan(2);
    expect(right.y).toBeGreaterThan(left.y);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
});

test.describe("component selection", () => {
  test("options show key specs with units, fidelity badge, provenance and cost delta", async ({ page }) => {
    await openArchitect(page);
    await page.getByTestId("category-nav-communications").click();
    const medium = page.getByTestId("option-comms-xband-medium");
    await expect(medium).toContainText(/bit\/s/);
    await expect(medium.getByTestId("fidelity-badge-gameplay-estimate").first()).toBeVisible();
    await medium.getByRole("button", { name: /show provenance/i }).first().click();
    await expect(page.getByTestId("provenance-panel")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(medium.getByTestId("cost-delta")).toContainText(/catalogue list cost delta/i);
    await expect(medium.getByTestId("cost-delta")).toContainText(/[+-]|no change/i);
    await expect(page.getByTestId("selected-component")).toContainText(/low/i);
  });

  test("an instrument toggles in place and stays a multi-select", async ({ page }) => {
    const id = await openArchitect(page);
    await choose(page, "instrument", "inst-thermal-ir");
    await expect(page.getByTestId("revision-pill")).toHaveText("Revision 1");
    const s = await stored(page, id);
    expect(s.architecture.instrumentIds).toEqual(
      expect.arrayContaining(["inst-hires-camera", "inst-vnir-spectrometer", "inst-thermal-ir"]),
    );
  });

  test("keyboard only: a component swap completes without a pointer", async ({ page }) => {
    const id = await openArchitect(page);
    await page.getByTestId("category-nav-communications").focus();
    await page.keyboard.press("Enter");
    const target = "select-comms-xband-medium";
    let reached = false;
    for (let i = 0; i < 200 && !reached; i += 1) {
      await page.keyboard.press("Tab");
      reached = (await page.evaluate(() => document.activeElement?.getAttribute("data-testid"))) === target;
    }
    expect(reached).toBe(true);
    await page.keyboard.press("Enter");
    // the replace confirmation opens with focus on its confirm button
    await expect(page.getByTestId("change-dialog")).toBeVisible();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("revision-pill")).toHaveText("Revision 1");
    expect((await stored(page, id)).architecture.communicationsId).toBe("comms-xband-medium");
  });
});

test.describe("NEO demo: weak radio to medium radio", () => {
  test("link-margin fail and data-return warning clear after the swap; mission becomes ready", async ({ page }) => {
    await openArchitect(page);
    await expect(page.getByTestId("constraint-card-link-margin")).toHaveAttribute("data-status", "fail");
    await expect(page.getByTestId("constraint-card-data-return")).toHaveAttribute("data-status", "warning");
    await expect(page.getByTestId("feasibility-badge")).toHaveText(/infeasible/i);
    await expect(page.getByTestId("mission-ready-badge")).toHaveText(/not mission-ready/i);

    await choose(page, "communications", "comms-xband-medium");
    await expect(page.getByTestId("analysis-revision")).toContainText(/revision 1/i);
    await expect(page.getByTestId("constraint-card-link-margin")).toHaveAttribute("data-status", "pass");
    await expect(page.getByTestId("constraint-card-data-return")).toHaveAttribute("data-status", "pass");
    await expect(page.getByTestId("feasibility-badge")).toHaveText(/^feasible$/i);
    await expect(page.getByTestId("mission-ready-badge")).toHaveText(/^mission-ready$/i);
  });

  test("the swap highlights affected budget tiles (mass, power, data)", async ({ page }) => {
    await openArchitect(page);
    for (const t of ["mass", "power", "data"]) {
      await expect(page.getByTestId(`budget-tile-${t}`)).toHaveAttribute("data-changed", "false");
    }
    await choose(page, "communications", "comms-xband-medium");
    await expect(page.getByTestId("analysis-revision")).toContainText(/revision 1/i);
    for (const t of ["mass", "power", "data"]) {
      const tile = page.getByTestId(`budget-tile-${t}`);
      await expect(tile).toHaveAttribute("data-changed", "true");
      await expect(tile.getByTestId("changed-marker")).toBeVisible();
    }
  });
});

test.describe("constraint panel", () => {
  test("a failing constraint shows actual, limit, margin, impacted subsystem and an action", async ({ page }) => {
    await openArchitect(page);
    const card = page.getByTestId("constraint-card-link-margin");
    await expect(card.getByTestId("constraint-badge-fail")).toBeVisible();
    await expect(card.getByTestId("constraint-actual")).not.toHaveText(/^\s*$/);
    await expect(card.getByTestId("constraint-limit")).not.toHaveText(/^\s*$/);
    await expect(card.getByTestId("constraint-margin")).toBeVisible();
    await expect(card.getByTestId("constraint-impacted")).not.toHaveText(/^\s*$/);
    expect(await card.getByTestId("constraint-action").count()).toBeGreaterThanOrEqual(1);
  });

  test("not-modelled constraints are shown distinctly and never as pass", async ({ page }) => {
    await openArchitect(page);
    const nm = page.locator('[data-testid^="constraint-card-"][data-status="not-modelled"]');
    expect(await nm.count()).toBeGreaterThan(0);
    await expect(nm.first().getByTestId("constraint-badge-not-modelled")).toBeVisible();
    await expect(nm.first()).toContainText(/not modelled/i);
  });

  test("explain opens the bottom drawer with explanation, assumptions and recent changes", async ({ page }) => {
    await openArchitect(page);
    await choose(page, "communications", "comms-xband-medium");
    await expect(page.getByTestId("analysis-revision")).toContainText(/revision 1/i);
    await choose(page, "communications", "comms-xband-lowgain");
    await expect(page.getByTestId("analysis-revision")).toContainText(/revision 2/i);
    const card = page.getByTestId("constraint-card-link-margin");
    const explanation = (await card.getByTestId("constraint-explanation").textContent())!.trim();
    await card.getByRole("button", { name: /explain/i }).click();
    const drawer = page.getByTestId("bottom-drawer");
    await expect(drawer.getByTestId("drawer-explanation")).toContainText(explanation);
    expect(await drawer.getByTestId("drawer-assumption").count()).toBeGreaterThan(0);
    await expect(drawer.getByTestId("drawer-change").first()).toContainText(/communications/i);
    expect(await drawer.getByTestId("drawer-change").count()).toBe(2);
  });
});

test.describe("compatibility confirmation", () => {
  test("a swap that breaks another selection asks first and never edits it silently", async ({ page }) => {
    const id = await openArchitect(page);
    await page.getByTestId("category-nav-bus").click();
    await expect(page.getByTestId("option-bus-12u")).toContainText(/conflicts with/i);
    await page.getByTestId("select-bus-12u").click();
    const dialog = page.getByTestId("compat-dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText(/high-resolution camera/i);
    expect((await stored(page, id)).architecture.busId).toBe("bus-27u"); // nothing changed yet
    await dialog.getByRole("button", { name: /cancel/i }).click();
    await expect(dialog).toHaveCount(0);
    expect((await stored(page, id)).architecture.busId).toBe("bus-27u");
    await expect(page.getByTestId("revision-pill")).toHaveText("Revision 0");

    await page.getByTestId("select-bus-12u").click();
    await page.getByTestId("compat-dialog").getByRole("button", { name: /swap anyway/i }).click();
    await expect(page.getByTestId("revision-pill")).toHaveText("Revision 1");
    const s = await stored(page, id);
    expect(s.architecture.busId).toBe("bus-12u");
    expect(s.architecture.instrumentIds).toContain("inst-hires-camera"); // dependent selection untouched
    await expect(page.getByTestId("analysis-revision")).toContainText(/revision 1/i);
    await expect(page.locator('[data-testid^="constraint-card-compat-"][data-status="fail"]').first()).toBeVisible();
  });
});

test.describe("stale-response protection", () => {
  test("a delayed revision-1 response never overwrites revision 2", async ({ page }) => {
    await openArchitect(page);
    let rev2Mass: string | null = null;
    await page.route(VALIDATE, async (route) => {
      const rev = route.request().postDataJSON().missionState.designRevision as number;
      const response = await route.fetch();
      if (rev === 1) await new Promise((r) => setTimeout(r, 2500));
      await route.fulfill({ response }).catch(() => {});
    });
    await choose(page, "communications", "comms-xband-medium"); // revision 1 (slow)
    await page.waitForTimeout(400);
    await choose(page, "thermal", "thermal-active"); // revision 2 (fast)
    await expect(page.getByTestId("analysis-revision")).toContainText(/revision 2/i);
    rev2Mass = await page.getByTestId("budget-tile-mass").textContent();
    await page.waitForTimeout(3200); // the late revision-1 response has now arrived
    await expect(page.getByTestId("analysis-revision")).toContainText(/revision 2/i);
    expect(await page.getByTestId("budget-tile-mass").textContent()).toBe(rev2Mass);
  });

  test("the store rejects a stale revision and bumps the revision on commit", async ({ page }) => {
    const id = await openArchitect(page);
    const result = await page.evaluate(() => {
      const store = (window as unknown as { __missionStore: { getState: () => Record<string, unknown> } }).__missionStore;
      const s = store.getState() as {
        analysis: { designRevision: number };
        applyAnalysis: (a: unknown) => boolean;
        selectComponent: (c: string, id: string) => void;
        commitRevision: () => void;
        designRevision: number;
        mission: { architecture: { instrumentIds: string[] } };
      };
      const base = s.analysis;
      const before = s.designRevision;
      s.selectComponent("instrument", "inst-thermal-ir");
      const added = store.getState() as typeof s;
      const hasAfterToggle = added.mission.architecture.instrumentIds.includes("inst-thermal-ir");
      s.selectComponent("instrument", "inst-thermal-ir");
      const removed = (store.getState() as typeof s).mission.architecture.instrumentIds.includes("inst-thermal-ir");
      s.selectComponent("instrument", "inst-thermal-ir");
      s.commitRevision();
      const after = (store.getState() as typeof s).designRevision;
      const staleAccepted = s.applyAnalysis({ ...base, designRevision: before }); // now behind
      const wrongMission = s.applyAnalysis({ ...base, designRevision: after, missionId: "mission-other" });
      return { before, after, hasAfterToggle, removed, staleAccepted, wrongMission };
    });
    expect(result.hasAfterToggle).toBe(true);
    expect(result.removed).toBe(false);
    expect(result.after).toBe(result.before + 1);
    expect(result.staleAccepted).toBe(false);
    expect(result.wrongMission).toBe(false);
    expect((await stored(page, id)).designRevision).toBe(result.after);
  });

  test("an API failure keeps the last good numbers, marked stale, with Retry", async ({ page }) => {
    await openArchitect(page);
    const massBefore = (await page.getByTestId("budget-tile-mass").textContent()) ?? "";
    await page.route(VALIDATE, (route) =>
      route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ ok: false }) }),
    );
    await choose(page, "communications", "comms-xband-medium");
    const failed = page.getByTestId("analysis-failed");
    await expect(failed).toContainText(/analysis failed/i);
    await expect(failed.getByRole("button", { name: /retry/i })).toBeVisible();
    await expect(page.getByTestId("stale-badge")).toBeVisible();
    const mass = page.getByTestId("budget-tile-mass");
    await expect(mass).toContainText(/\d\s?kg/);
    await expect(mass).toHaveText(massBefore); // last good numbers unchanged, not zeroed
    await expect(page.getByTestId("analysis-revision")).toContainText(/revision 0/i);
    await page.unroute(VALIDATE);
    await failed.getByRole("button", { name: /retry/i }).click();
    await expect(page.getByTestId("analysis-revision")).toContainText(/revision 1/i);
    await expect(page.getByTestId("analysis-failed")).toHaveCount(0);
    await expect(page.getByTestId("stale-badge")).toHaveCount(0);
  });

  test("with no analysis ever received, tiles show a dash and a reason, never 0", async ({ page }) => {
    await page.route(VALIDATE, (route) => route.abort());
    const id = await startNeo(page);
    await page.goto(`/architect/${id}`);
    await expect(page.getByTestId("analysis-failed")).toBeVisible({ timeout: 30_000 });
    const tile = page.getByTestId("budget-tile-mass");
    await expect(tile).toContainText("—");
    await expect(tile.getByTestId("missing-reason").first()).toContainText(/analysis/i);
    await expect(tile).not.toContainText(/\b0\s?kg/);
  });
});

test.describe("placeholder analysis and debounce", () => {
  test("a failed-shaped analysis shows dashes and reasons, never 0 kg or 0 %", async ({ page }) => {
    const id = await startNeo(page);
    await page.route(VALIDATE, async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      const a = body.data.analysis;
      const placeholder = {
        fidelity: "not-modelled",
        sourceName: "MISSIONFORGE analysis",
        assumptions: ["Analysis could not run; placeholder value, not a result."],
      };
      for (const [k, v] of Object.entries(a.budgets)) {
        if (v && typeof v === "object") {
          a.budgets[k] = { value: 0, unit: (v as { unit: string }).unit, provenance: placeholder };
        } else {
          a.budgets[k] = 0;
        }
      }
      a.science = { ...a.science, coverageScore: 0, collectedFraction: 0, returnedFraction: 0 };
      a.constraints = [
        {
          id: "catalog-item-not-found",
          label: "Catalogue item not found",
          status: "fail",
          severity: 3,
          explanation: "Analysis could not run: unknown id.",
          impactedSubsystems: ["architecture"],
          suggestedActions: [{ actionId: "select-catalog-component", label: "Select an existing component", expectedEffect: "Lets the analysis run." }],
        },
      ];
      a.feasibility = "infeasible";
      a.missionReady = false;
      a.topDrivers = ["catalog-item-not-found"];
      await route.fulfill({ response, json: body });
    });
    await page.goto(`/architect/${id}`);
    await expect(page.getByTestId("constraint-card-catalog-item-not-found")).toBeVisible({ timeout: 30_000 });
    for (const t of ["mass", "power", "deltav", "data", "cost", "science"]) {
      const tile = page.getByTestId(`budget-tile-${t}`);
      await expect(tile).toContainText("—");
      await expect(tile.getByTestId("missing-reason").first()).toContainText(/could not run/i);
      await expect(tile.locator('[data-testid^="fidelity-badge-"]')).toHaveCount(0);
    }
    const panel = page.getByTestId("budget-panel");
    await expect(panel).not.toContainText(/\b0\s?(kg|%|W|km\/s|bit|USD)/);
  });

  test("two edits within the debounce window send one request, for the latest revision", async ({ page }) => {
    await openArchitect(page);
    const revisions: number[] = [];
    await page.route(VALIDATE, async (route) => {
      revisions.push(route.request().postDataJSON().missionState.designRevision);
      await route.continue();
    });
    await page.evaluate(() => {
      const store = (window as unknown as { __missionStore: { getState: () => { selectComponent: (c: string, id: string) => void; commitRevision: () => void } } }).__missionStore;
      const s = store.getState();
      s.selectComponent("communications", "comms-xband-medium");
      s.commitRevision();
      setTimeout(() => {
        s.selectComponent("thermal", "thermal-active");
        s.commitRevision();
      }, 40);
    });
    await expect(page.getByTestId("analysis-revision")).toContainText(/revision 2/i);
    await page.waitForTimeout(600);
    expect(revisions).toEqual([2]);
  });
});

test.describe("undefined margins (R38)", () => {
  test("an empty observation plan shows the data margin as a dash with a reason, never 0 %", async ({ page }) => {
    const id = await startNeo(page);
    // Real backend; only the request is edited so the design has no observations.
    await page.route(VALIDATE, async (route) => {
      const body = route.request().postDataJSON();
      body.missionState.operations.observationPlan = [];
      await route.continue({ postData: JSON.stringify(body) });
    });
    await page.goto(`/architect/${id}`);
    await expect(page.getByTestId("analysis-revision")).toContainText(/revision 0/i, { timeout: 30_000 });
    const tile = page.getByTestId("budget-tile-data");
    const margin = tile.locator("div", { has: page.getByText("Downlink margin", { exact: true }) }).last();
    await expect(margin).toContainText("—");
    await expect(margin.getByTestId("missing-reason")).toContainText(/not defined/i);
    await expect(margin).not.toContainText(/0(\.0)?\s?%/);
  });
});

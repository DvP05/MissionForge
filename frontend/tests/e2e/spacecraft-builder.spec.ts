import { expect, test, type Page } from "@playwright/test";

/**
 * Frontend rebuild (front_design.md): 3D spacecraft builder, inspector, live engineering
 * dashboard, science lab, archive. Engineering values must come from the backend analysis
 * of the current revision; the 3D view follows the canonical MissionState.
 */

async function startNeo(page: Page): Promise<string> {
  await page.goto("/");
  await page.getByTestId("scenario-card-neo-rendezvous").getByRole("button", { name: /start mission/i }).click();
  await page.waitForURL(/\/mission\/mission-[0-9a-f]{12}$/);
  return new URL(page.url()).pathname.split("/").pop() as string;
}

async function openArchitect(page: Page): Promise<string> {
  const id = await startNeo(page);
  await page.goto(`/architect/${id}`);
  await expect(page.getByTestId("analysis-revision")).toContainText(/revision 0/i, { timeout: 30_000 });
  return id;
}

test.describe("spacecraft architect", () => {
  test("the viewport renders the installed parts of the canonical design", async ({ page }) => {
    await openArchitect(page);
    const stage = page.getByTestId("spacecraft-stage");
    await expect(stage).toBeVisible();
    // 3D canvas, or the 2D schematic where WebGL is unavailable
    await expect(stage.locator("canvas, [data-testid='spacecraft-schematic-2d']").first()).toBeVisible({ timeout: 30_000 });
    const parts = page.getByTestId("part-list");
    await expect(parts.getByTestId("part-comms-xband-lowgain")).toBeVisible();
    await expect(parts.getByTestId("part-inst-hires-camera")).toBeVisible();
    // the ground segment is not on the spacecraft
    await expect(parts.locator("[data-testid^='part-ground-']")).toHaveCount(0);
    await expect(stage).toContainText(/illustrative placeholder geometry/i);
  });

  test("installing a high-gain antenna changes the spacecraft, the inspector and the analysed link", async ({ page }) => {
    const id = await openArchitect(page);
    const linkBefore = await page.getByTestId("dash-link").textContent();

    await page.getByTestId("category-nav-communications").click();
    await page.getByTestId("select-comms-xband-highgain").click();
    await page.getByTestId("confirm-change").click();
    await expect(page.getByTestId("revision-pill")).toHaveText("Revision 1");

    // canonical state first: the saved design names the new antenna
    const saved = await page.evaluate((key) => JSON.parse(localStorage.getItem(key) as string), `missionforge:mission:${id}`);
    expect(saved.architecture.communicationsId).toBe("comms-xband-highgain");

    // the 3D part list follows it, the old antenna is gone, the inspector shows the new one
    await expect(page.getByTestId("part-comms-xband-highgain")).toBeVisible();
    await expect(page.getByTestId("part-comms-xband-lowgain")).toHaveCount(0);
    await page.getByTestId("panel-tab-details").click();
    await expect(page.getByTestId("inspector-name")).toContainText(/high-gain/i);
    await expect(page.getByTestId("inspector-specs")).toContainText(/dB/);

    // the dashboard shows the backend analysis of revision 1 (never a browser estimate)
    await expect(page.getByTestId("dashboard-revision")).toContainText("Analysis of revision 1", { timeout: 30_000 });
    await expect(page.getByTestId("dash-link")).not.toHaveText(linkBefore ?? "");
  });

  test("a stale analysis response cannot overwrite a newer revision", async ({ page }) => {
    await openArchitect(page);
    let first = true;
    await page.route("**/api/mission/validate", async (route) => {
      if (first) {
        first = false;
        await new Promise((r) => setTimeout(r, 2500)); // the revision-1 answer arrives late
      }
      await route.continue();
    });
    await page.getByTestId("category-nav-communications").click();
    await page.getByTestId("select-comms-xband-medium").click();
    await page.getByTestId("confirm-change").click();
    await page.getByTestId("select-comms-xband-highgain").click();
    await page.getByTestId("confirm-change").click();
    await expect(page.getByTestId("revision-pill")).toHaveText("Revision 2");
    await expect(page.getByTestId("dashboard-revision")).toContainText("Analysis of revision 2", { timeout: 30_000 });
    await page.waitForTimeout(3000);
    await expect(page.getByTestId("dashboard-revision")).toContainText("Analysis of revision 2");
  });

  test("instruments install and remove from the inspector; selecting a part inspects it", async ({ page }) => {
    await openArchitect(page);
    await page.getByTestId("part-inst-vnir-spectrometer").click();
    await expect(page.getByTestId("inspector-name")).toContainText(/spectrometer/i);
    await page.getByTestId("inspector-remove").click();
    // removing the only VNIR instrument names the measurement it leaves uncovered
    await expect(page.getByTestId("change-lost")).toContainText(/VNIR/i);
    await page.getByTestId("confirm-change").click();
    await expect(page.getByTestId("revision-pill")).toHaveText("Revision 1");
    await expect(page.getByTestId("part-inst-vnir-spectrometer")).toHaveCount(0);

    await page.getByTestId("category-nav-instrument").click();
    await page.getByTestId("inspect-inst-thermal-ir").click();
    await expect(page.getByTestId("inspector-name")).toContainText(/thermal/i);
    await page.getByTestId("inspector-install").click();
    const ask = page.getByTestId("confirm-change");
    await ask.waitFor({ state: "visible", timeout: 1500 }).then(() => ask.click(), () => undefined);
    await expect(page.getByTestId("revision-pill")).toHaveText("Revision 2");
    await expect(page.getByTestId("part-inst-thermal-ir")).toBeVisible();
  });

  test("view modes and overlays are real controls with honest notes", async ({ page }) => {
    await openArchitect(page);
    await page.getByTestId("view-mode-exploded").click();
    await expect(page.getByTestId("view-mode-exploded")).toHaveAttribute("aria-pressed", "true");
    await page.getByTestId("view-mode-power").click();
    await expect(page.getByTestId("view-mode-note")).toContainText(/visual highlight .* no power-flow simulation/i);
    await page.getByTestId("view-mode-technical").click();
    await expect(page.getByTestId("toggle-labels")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("toggle-mounts")).toHaveAttribute("aria-pressed", "true");
    await page.getByTestId("camera-top").click();
    await page.getByTestId("camera-reset").click();
  });

  test("the dashboard never shows a number for an unmodelled metric", async ({ page }) => {
    await openArchitect(page);
    const cells = page.locator("[data-testid^='dash-']").filter({ has: page.locator("[data-status='NOT MODELLED']") });
    const n = await cells.count();
    for (let i = 0; i < n; i += 1) {
      await expect(cells.nth(i)).not.toContainText(/^\s*0(\.0+)?\s*$/);
    }
  });
});

test("science lab links objectives to installed instruments and highlights them", async ({ page }) => {
  const id = await startNeo(page);
  await page.goto(`/science/${id}`);
  const lab = page.getByTestId("science-lab");
  await expect(lab).toBeVisible();
  await expect(page.getByTestId("lab-measurement-meas-vnir-spectra")).toContainText(/spectrometer/i);
  await page.getByTestId("lab-focus-obj-composition").click();
  await expect(page.getByTestId("view-mode-note")).toContainText(/spectral composition/i);
  await expect(page.getByTestId("lab-coverage-obj-composition")).toContainText(/coverage/i, { timeout: 30_000 });
});

test("archive lists saved missions with their flow links", async ({ page }) => {
  const id = await startNeo(page);
  await page.goto("/archive");
  const entry = page.getByTestId(`archive-mission-${id}`);
  await expect(entry).toBeVisible();
  await expect(entry.getByRole("link", { name: "Science lab" })).toHaveAttribute("href", `/science/${id}`);
  await page.goto("/");
  await expect(page.getByTestId("saved-missions")).toContainText(/echoes of origins/i);
});

test("the hangar does not load the 3D engine", async ({ page }) => {
  const scripts: string[] = [];
  page.on("response", async (r) => {
    if (r.request().resourceType() === "script") scripts.push(await r.text().catch(() => ""));
  });
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  expect(scripts.length).toBeGreaterThan(0);
  expect(scripts.some((s) => s.includes("WebGLRenderer"))).toBe(false);
});

test("no two installed parts overlap, for every bus size with the largest parts and all instruments", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("missionforge:motion", "reduced"));
  await openArchitect(page);
  await page.getByTestId("spacecraft-stage").locator("canvas").waitFor({ timeout: 30_000 });
  await page.waitForFunction(() => typeof (window as unknown as { __spacecraftOverlaps?: unknown }).__spacecraftOverlaps === "function");
  const all = ["inst-wide-camera", "inst-hires-camera", "inst-vnir-spectrometer", "inst-thermal-ir", "inst-magnetometer"];
  for (const busId of ["bus-12u", "bus-27u", "bus-espa"]) {
    const overlaps = await page.evaluate(
      async ([bus, instruments]) => {
        const w = window as unknown as {
          __missionStore: { getState: () => { mission: { architecture: Record<string, unknown> }; restoreArchitecture: (a: unknown) => void } };
          __spacecraftOverlaps: () => string[];
        };
        const s = w.__missionStore.getState();
        s.restoreArchitecture({
          ...s.mission.architecture,
          busId: bus,
          powerId: "power-xl",
          communicationsId: "comms-kaband-highgain",
          propulsionId: "prop-biprop",
          adcsId: "adcs-precision",
          thermalId: "thermal-active",
          cdhId: "cdh-large",
          instrumentIds: instruments,
        });
        await new Promise((r) => setTimeout(r, 800));
        return w.__spacecraftOverlaps();
      },
      [busId, all] as const,
    );
    expect(overlaps, `${busId}: ${overlaps.join("; ")}`).toEqual([]);
  }
});

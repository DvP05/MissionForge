import { readFileSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

const NEO = "scenario-card-neo-rendezvous";
const MISSION_KEY = (id: string) => `missionforge:mission:${id}`;

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

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

async function pickMediumComms(page: Page) {
  await page.getByTestId("category-nav-communications").click();
  await page.getByTestId("select-comms-xband-medium").click();
  await page.getByTestId("confirm-change").click();
  await expect(page.getByTestId("analysis-revision")).toContainText(/revision 1/i);
}

/** Feasible design, launched; returns ids. The run is cached in this browser. */
async function launchFeasible(page: Page): Promise<{ missionId: string; runId: string }> {
  const missionId = await openArchitect(page);
  await pickMediumComms(page);
  await expect(page.getByTestId("mission-ready-badge")).toHaveText(/^mission-ready$/i);
  await page.getByTestId("launch-button").click();
  await page.waitForURL(/\/control\/[^/]+/, { timeout: 30_000 });
  await expect(page.getByTestId("mission-control")).toBeVisible();
  return { missionId, runId: new URL(page.url()).pathname.split("/").pop() as string };
}

const storeMission = async (page: Page): Promise<Json> => {
  await page.waitForFunction(() => Boolean((window as any).__missionStore?.getState().mission)); // eslint-disable-line @typescript-eslint/no-explicit-any
  return page.evaluate(() => (window as any).__missionStore.getState().mission); // eslint-disable-line @typescript-eslint/no-explicit-any
};

async function exportPackage(page: Page): Promise<Json> {
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByTestId("export-package").click()]);
  return JSON.parse(readFileSync(await download.path(), "utf8")) as Json;
}

const upload = (page: Page, name: string, data: string | Buffer) =>
  page.getByTestId("import-package-input").setInputFiles({
    name,
    mimeType: "application/json",
    buffer: typeof data === "string" ? Buffer.from(data) : data,
  });

test.describe("persistence", () => {
  test("reload restores the latest design", async ({ page }) => {
    const id = await openArchitect(page);
    await pickMediumComms(page);
    await page.goto(`/mission/${id}`);
    await page.reload();
    await expect(page.getByTestId("revision-pill")).toHaveText(/revision 1/i);
    await expect(page.getByTestId("save-status")).toContainText(/saved in this browser/i);
    expect((await storeMission(page)).architecture.communicationsId).toBe("comms-xband-medium");
  });

  test("export then import elsewhere restores the identical MissionState and the run", async ({ page }) => {
    const { missionId, runId } = await launchFeasible(page);
    await page.goto(`/mission/${missionId}`);
    const original = await storeMission(page);
    const pkg = await exportPackage(page);
    expect(pkg.packageSchemaVersion).toBe("1.0");
    expect(pkg.manifest).toMatchObject({ engineVersion: expect.any(String), catalogVersion: expect.any(String) });
    expect(pkg.mission).toEqual(original);
    expect(pkg.runs.map((r: Json) => r.runId)).toEqual([runId]);
    expect(pkg.runs[0].analysis).toBeUndefined(); // derived data is not exported with runs

    // "Elsewhere": a browser with nothing saved.
    await page.evaluate(() => window.localStorage.clear());
    await page.goto("/");
    await upload(page, "package.json", JSON.stringify(pkg));
    await page.waitForURL(new RegExp(`/mission/${missionId}$`));
    await expect(page.getByTestId("workspace-title")).toBeVisible();
    expect(await storeMission(page)).toEqual(original);
    await expect(page.getByTestId(`run-row-${runId}`)).toBeVisible();
    await expect(page.getByTestId(`run-status-${runId}`)).toHaveText(/versions match.*replay can be verified/i);
    await expect(page.getByText(/identical replay/i)).toHaveCount(0); // not proven until Verify replay
    await expect(page.getByTestId("replay-mismatch-banner")).toHaveCount(0);
    // reload keeps it
    await page.reload();
    expect((await storeMission(page)).designRevision).toBe(original.designRevision);
    await page.goto(`/control/${runId}`);
    await expect(page.getByTestId("mission-control")).toBeVisible();
  });

  test("hostile and corrupt files are rejected with an explanation and change nothing", async ({ page }) => {
    const id = await openArchitect(page);
    await pickMediumComms(page);
    await page.goto(`/mission/${id}`);
    const pkg = await exportPackage(page);
    const before = await page.evaluate((k) => window.localStorage.getItem(k), MISSION_KEY(id));
    expect(before).toBeTruthy();

    const nan = JSON.stringify(pkg).replace(/"randomSeed":(-?\d+)/, '"randomSeed":NaN');
    expect(nan).toContain("NaN");
    const wrongSchema = { ...pkg, mission: { ...pkg.mission, schemaVersion: "9.9" } };
    const cases: [string, string | Buffer, RegExp][] = [
      ["broken.json", "{ this is not json", /not valid json/i],
      ["schema.json", JSON.stringify({ schemaVersion: "9.9" }), /package format/i],
      ["wrong-mission-schema.json", JSON.stringify(wrongSchema), /schema version/i],
      ["nan.json", nan, /not valid json/i],
      ["huge.json", Buffer.alloc(20 * 1024 * 1024, "a"), /larger than|import limit/i],
    ];
    for (const [name, data, message] of cases) {
      await upload(page, name, data);
      const error = page.getByTestId("import-error");
      await expect(error).toBeVisible();
      await expect(page.getByTestId("import-error-message")).toHaveText(message);
      await expect(page.getByTestId("import-error-message")).toContainText(/nothing was changed/i);
      expect(await page.evaluate((k) => window.localStorage.getItem(k), MISSION_KEY(id))).toBe(before);
      expect((await storeMission(page)).missionId).toBe(id);
      expect(page.url()).toContain(`/mission/${id}`);
      await error.getByRole("button", { name: /dismiss/i }).click();
    }
  });

  test("HTML in a title is sanitised and never rendered as markup", async ({ page }) => {
    const id = await openArchitect(page);
    await page.goto(`/mission/${id}`);
    const pkg = await exportPackage(page);
    pkg.mission.missionId = "mission-aaaaaaaaaaaa";
    pkg.mission.title = 'Hostile <img src=x onerror="window.__pwned=1"> title <script>window.__pwned=1</script>';
    await upload(page, "hostile.json", JSON.stringify(pkg));
    await page.waitForURL(/\/mission\/mission-aaaaaaaaaaaa$/);
    const title = page.getByTestId("workspace-title");
    await expect(title).toBeVisible();
    await expect(title).not.toContainText("<");
    await expect(title).not.toContainText("onerror");
    await expect(title).toContainText("Hostile");
    await expect(page.locator("img[onerror]")).toHaveCount(0);
    expect(await page.evaluate(() => (window as any).__pwned)).toBeUndefined(); // eslint-disable-line @typescript-eslint/no-explicit-any
  });

  test("a different local copy of the same mission needs consent before it is replaced", async ({ page }) => {
    const id = await openArchitect(page);
    await page.goto(`/mission/${id}`);
    const pkg = await exportPackage(page); // revision 0
    await page.goto(`/architect/${id}`);
    await pickMediumComms(page); // local copy moves on to revision 1
    await page.goto(`/mission/${id}`);
    await upload(page, "old.json", JSON.stringify(pkg));
    await expect(page.getByTestId("import-conflict")).toBeVisible();
    await page.getByTestId("import-conflict-cancel").click();
    expect((await storeMission(page)).designRevision).toBe(1);
    await upload(page, "old.json", JSON.stringify(pkg));
    await page.getByTestId("import-conflict-replace").click();
    await expect(page.getByTestId("revision-pill")).toHaveText(/revision 0/i);
  });

  test("a storage quota error shows an export prompt and the UI keeps working", async ({ page }) => {
    const id = await openArchitect(page);
    await page.goto(`/mission/${id}`);
    await page.evaluate(() => {
      Storage.prototype.setItem = function () {
        throw new DOMException("quota", "QuotaExceededError");
      };
    });
    await page.getByRole("link", { name: "Architect", exact: true }).click();
    await expect(page.getByTestId("analysis-revision")).toBeVisible({ timeout: 30_000 });
    await pickMediumComms(page); // revision 1 is committed in memory; the save fails
    await expect(page.getByTestId("revision-pill")).toHaveText(/revision 1/i);
    await page.getByRole("link", { name: "Brief", exact: true }).click();
    await expect(page.getByTestId("save-status")).toContainText(/not saved/i);
    const prompt = page.getByTestId("storage-export-prompt");
    await expect(prompt).toContainText(/export a package/i);
    // the page still works, and the prompt's export yields the in-memory (unsaved) design
    const [download] = await Promise.all([page.waitForEvent("download"), page.getByTestId("storage-export-button").click()]);
    const pkg = JSON.parse(readFileSync(await download.path(), "utf8")) as Json;
    expect(pkg.mission.designRevision).toBe(1);
    expect(pkg.mission.architecture.communicationsId).toBe("comms-xband-medium");
  });
});

test.describe("run cache", () => {
  test("legacy cached runs outside the LRU index are adopted and the bound is enforced", async ({ page }) => {
    const { missionId, runId } = await launchFeasible(page);
    await page.evaluate(
      ([id]) => {
        const raw = window.localStorage.getItem(`missionforge:run:${id}`) as string;
        window.localStorage.removeItem("missionforge:run-index"); // pre-index (legacy) state
        for (let i = 0; i < 8; i += 1) {
          const copy = JSON.parse(raw);
          copy.run.runId = `run-legacy-${i}`;
          window.localStorage.setItem(`missionforge:run:run-legacy-${i}`, JSON.stringify(copy));
        }
      },
      [runId],
    );
    await page.goto(`/mission/${missionId}`);
    await expect(page.getByTestId("runs-panel")).toBeVisible();
    const state = await page.evaluate(() => ({
      keys: Object.keys(window.localStorage).filter((k) => k.startsWith("missionforge:run:")),
      index: JSON.parse(window.localStorage.getItem("missionforge:run-index") ?? "[]") as string[],
    }));
    expect(state.keys.length).toBeLessThanOrEqual(6); // 9 stored, bound is 6
    expect(state.index.length).toBe(state.keys.length); // every stored run is indexed
  });
});

test.describe("replay", () => {
  test("an imported run made with a different engine says version mismatch, never identical", async ({ page }) => {
    const { missionId, runId } = await launchFeasible(page);
    await page.goto(`/mission/${missionId}`);
    const pkg = await exportPackage(page);
    pkg.runs[0].engineVersion = "9.9.9";
    pkg.runs[0].manifest.engineVersion = "9.9.9";
    await page.evaluate(() => window.localStorage.clear());
    await page.goto("/");
    await upload(page, "other-engine.json", JSON.stringify(pkg));
    await page.waitForURL(new RegExp(`/mission/${missionId}$`));
    const banner = page.getByTestId("replay-mismatch-banner");
    await expect(banner).toContainText(/version mismatch/i);
    await expect(banner).toContainText(/not an identical replay/i);
    const status = page.getByTestId(`run-status-${runId}`);
    await expect(status).toContainText(/not an identical replay/i);
    await expect(status).toContainText(/engineVersion: recorded 9\.9\.9/);
    await expect(page.getByText(/^identical replay/i)).toHaveCount(0);
    // explicit replay does not claim identity either
    await page.getByTestId(`run-verify-${runId}`).click();
    await expect(page.getByTestId(`run-replay-result-${runId}`)).toContainText(/not an identical replay/i);
    await expect(page.getByText(/^identical replay/i)).toHaveCount(0);
    await page.goto(`/control/${runId}`);
    await expect(page.getByTestId("run-version-banner")).toContainText(/not an identical replay/i);
  });

  test("same versions replay to identical events, telemetry and decisions", async ({ page }) => {
    const { missionId, runId } = await launchFeasible(page);
    await page.goto(`/mission/${missionId}`);
    const pkg = await exportPackage(page);
    const recorded = pkg.runs[0] as Json;

    await page.evaluate(() => window.localStorage.clear());
    await page.goto("/");
    await upload(page, "same-versions.json", JSON.stringify(pkg));
    await page.waitForURL(new RegExp(`/mission/${missionId}$`));
    await expect(page.getByTestId(`run-status-${runId}`)).toHaveText(/replay can be verified/i);
    await page.getByTestId(`run-verify-${runId}`).click();
    await expect(page.getByTestId(`run-replay-result-${runId}`)).toContainText(/^Identical replay: re-running reproduced all/);
    await expect(page.getByTestId(`run-status-${runId}`)).toHaveText(/identical replay \(verified/i);

    // The server's re-run equals the recorded run: ids, order, telemetry, decisions.
    const res = await page.request.post("http://127.0.0.1:8000/api/mission/replay", { data: { run: recorded } });
    const body = (await res.json()) as Json;
    expect(body.ok).toBe(true);
    expect(body.data.identical).toBe(true);
    const rebuilt = body.data.run as Json;
    expect(rebuilt.events.map((e: Json) => e.id)).toEqual(recorded.events.map((e: Json) => e.id));
    expect(rebuilt.events.map((e: Json) => e.sequence)).toEqual(recorded.events.map((e: Json) => e.sequence));
    expect(rebuilt.telemetry).toEqual(recorded.telemetry);
    expect(rebuilt.decisions).toEqual(recorded.decisions);
    expect(rebuilt).toEqual(recorded);
  });

  test("tampered telemetry with matching versions imports as replayable but Verify says diverged", async ({ page }) => {
    const { missionId, runId } = await launchFeasible(page);
    await page.goto(`/mission/${missionId}`);
    const pkg = await exportPackage(page);
    pkg.runs[0].telemetry[0].value += 1;
    await page.evaluate(() => window.localStorage.clear());
    await page.goto("/");
    await upload(page, "tampered.json", JSON.stringify(pkg));
    await page.waitForURL(new RegExp(`/mission/${missionId}$`));
    await expect(page.getByTestId(`run-status-${runId}`)).toHaveText(/replay can be verified/i);
    await expect(page.getByText(/^identical replay/i)).toHaveCount(0);
    await page.getByTestId(`run-verify-${runId}`).click();
    await expect(page.getByTestId(`run-replay-result-${runId}`)).toContainText(/not an identical replay/i);
    await expect(page.getByTestId("replay-mismatch-banner")).toBeVisible();
    await expect(page.getByText(/^identical replay/i)).toHaveCount(0);
  });
});

test.describe("imported runs", () => {
  test("an imported run offers re-simulate instead of a decision that would 404", async ({ page }) => {
    const { missionId, runId } = await launchFeasible(page);
    await page.goto(`/mission/${missionId}`);
    const pkg = await exportPackage(page);
    await page.evaluate(() => window.localStorage.clear());
    await page.goto("/");
    await upload(page, "imported.json", JSON.stringify(pkg));
    await page.waitForURL(new RegExp(`/mission/${missionId}$`));
    await page.goto(`/control/${runId}`);
    await page.getByTestId("playback-play").click();
    const notice = page.getByTestId("imported-decision-notice");
    await expect(notice).toBeVisible({ timeout: 60_000 });
    await expect(notice).toContainText(/imported .* re-simulate to make decisions/i);
    await expect(page.getByTestId("decision-card")).toHaveCount(0);
    await notice.getByTestId("resimulate-run").click();
    await expect(page.getByTestId("decision-card")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("imported-decision-notice")).toHaveCount(0);
  });

  test("runs beyond the browser cache are reported, never silently dropped", async ({ page }) => {
    const { missionId } = await launchFeasible(page);
    await page.goto(`/mission/${missionId}`);
    const pkg = await exportPackage(page);
    const runs: Json[] = [];
    for (let seed = 1; seed <= 8; seed += 1) {
      const res = await page.request.post("http://127.0.0.1:8000/api/mission/simulate", {
        data: { missionState: pkg.mission, randomSeed: seed },
      });
      runs.push(((await res.json()) as Json).data.run);
    }
    pkg.runs = runs;
    await page.evaluate(() => window.localStorage.clear());
    await page.goto("/");
    await upload(page, "many.json", JSON.stringify(pkg));
    await page.waitForURL(new RegExp(`/mission/${missionId}$`));
    await expect(page.getByTestId("import-notice")).toContainText(/2 of 8 imported runs could not be kept/i);
    await expect(page.locator("[data-testid^='run-row-']")).toHaveCount(6);
    const keys = await page.evaluate(() => Object.keys(window.localStorage).filter((k) => k.startsWith("missionforge:replay:")));
    expect(keys.length).toBe(6); // no orphan replay records for dropped runs
  });
});

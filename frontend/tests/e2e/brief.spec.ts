import { expect, test, type Page } from "@playwright/test";

const NEO = "scenario-card-neo-rendezvous";

async function startNeo(page: Page): Promise<string> {
  await page.goto("/");
  await page.getByTestId(NEO).getByRole("button", { name: /start mission/i }).click();
  await page.waitForURL(/\/mission\/mission-[0-9a-f]{12}$/);
  return new URL(page.url()).pathname.split("/").pop() as string;
}

async function storedObjectiveIds(page: Page, id: string): Promise<string[]> {
  return page.evaluate((key) => {
    const raw = window.localStorage.getItem(key);
    const m = raw ? JSON.parse(raw) : null;
    return m ? m.scienceObjectives.map((o: { id: string }) => o.id) : [];
  }, `missionforge:mission:${id}`);
}

test.describe("mission brief (onboarding)", () => {
  test("shows scenario sentence, top-3 constraints, starter label, objectives and CTA", async ({
    page,
  }) => {
    const id = await startNeo(page);
    const narrative = (await page.getByTestId("brief-narrative").textContent()) ?? "";
    expect(narrative.trim()).toMatch(/^[^.!?]+[.!?]$/);
    await expect(page.getByTestId("brief-constraints").getByRole("listitem")).toHaveCount(3);
    await expect(page.getByTestId("starter-design-label")).toHaveText(/starter design/i);
    await expect(page.getByTestId("objective-selected-count")).toHaveText(/2 of 3/);
    await expect(page.getByTestId("objective-obj-morphology")).toBeVisible();
    await expect(page.getByTestId("objective-obj-composition")).toBeVisible();
    await expect(page.getByTestId("objective-obj-thermal")).toBeVisible();
    const cta = page.getByRole("link", { name: /continue to architect/i });
    await expect(cta).toHaveAttribute("href", `/architect/${id}`);
    await cta.click();
    await expect(page).toHaveURL(new RegExp(`/architect/${id}$`));
  });

  test("enabling and disabling optional objectives updates state, revision and storage", async ({
    page,
  }) => {
    const id = await startNeo(page);
    await expect(page.getByTestId("revision-pill")).toHaveText("Revision 0");
    const thermal = page.getByTestId("objective-obj-thermal").getByRole("checkbox");
    await thermal.check();
    await expect(page.getByTestId("objective-selected-count")).toHaveText(/3 of 3/);
    await expect(page.getByTestId("revision-pill")).toHaveText("Revision 1");
    expect(await storedObjectiveIds(page, id)).toContain("obj-thermal");
    await thermal.uncheck();
    await expect(page.getByTestId("revision-pill")).toHaveText("Revision 2");
    expect(await storedObjectiveIds(page, id)).not.toContain("obj-thermal");
  });

  test("the last remaining objective cannot be removed", async ({ page }) => {
    await startNeo(page);
    await page.getByTestId("objective-obj-composition").getByRole("checkbox").uncheck();
    const last = page.getByTestId("objective-obj-morphology").getByRole("checkbox");
    await expect(last).toBeDisabled();
  });

  test("objective priority can be edited", async ({ page }) => {
    const id = await startNeo(page);
    await page
      .getByTestId("objective-obj-composition")
      .getByLabel(/priority weight/i)
      .selectOption("2");
    await expect(page.getByTestId("revision-pill")).toHaveText("Revision 1");
    const priority = await page.evaluate((key) => {
      const m = JSON.parse(window.localStorage.getItem(key) as string);
      return m.scienceObjectives.find((o: { id: string }) => o.id === "obj-composition").priority;
    }, `missionforge:mission:${id}`);
    expect(priority).toBe(2);
  });

  test("landing to editable mission takes under 90 seconds", async ({ page }) => {
    const t0 = Date.now();
    await startNeo(page);
    await page.getByTestId("objective-obj-thermal").getByRole("checkbox").check();
    await expect(page.getByTestId("objective-selected-count")).toHaveText(/3 of 3/);
    const elapsed = Date.now() - t0;
    expect(elapsed).toBeLessThan(90_000);
  });

  test("concept card is dismissible and the dismissal is remembered", async ({ page }) => {
    await startNeo(page);
    const card = page.getByTestId("concept-card-lo1");
    await expect(card).toContainText(/science objectives become measurable requirements/i);
    await card.getByRole("button", { name: /dismiss/i }).click();
    await expect(card).toHaveCount(0);
    await page.reload();
    await expect(page.getByTestId("brief-narrative")).toBeVisible();
    await expect(page.getByTestId("concept-card-lo1")).toHaveCount(0);
  });

  test("concept card dismissal survives a storage failure for the flag", async ({ page }) => {
    await page.addInitScript(() => {
      const original = Storage.prototype.setItem;
      Storage.prototype.setItem = function (key: string, value: string) {
        if (key.includes("concept")) throw new Error("quota");
        return original.call(this, key, value);
      };
    });
    await startNeo(page);
    await page
      .getByTestId("concept-card-lo1")
      .getByRole("button", { name: /dismiss/i })
      .click();
    await expect(page.getByTestId("concept-card-lo1")).toHaveCount(0);
    await expect(page.getByTestId("brief-narrative")).toBeVisible();
  });

  test("brief has no horizontal overflow at 375 px", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await startNeo(page);
    await page.getByTestId("objective-obj-thermal").getByRole("checkbox").check();
    await expect(page.getByTestId("traceability-table")).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });
});

test.describe("science traceability", () => {
  test("lists objective -> requirement -> instrument and analyses via the backend", async ({
    page,
  }) => {
    const validate = page.waitForResponse(
      (r) => r.url().includes("/api/mission/validate") && r.request().method() === "POST",
    );
    await startNeo(page);
    await validate;
    const row = page.getByTestId("trace-row-meas-shape-model");
    await expect(row).toContainText("Surface morphology and shape");
    await expect(row).toContainText("shape-model");
    await expect(row).toContainText("high-resolution camera");
    await expect(page.getByTestId("trace-row-meas-vnir-spectra")).toContainText(
      "VNIR imaging spectrometer",
    );
    await expect(page.getByTestId("science-coverage")).toContainText("%");
    await expect(
      page.getByTestId("science-coverage").getByTestId("fidelity-badge-derived"),
    ).toBeVisible();
    await expect(page.getByTestId("trace-status-meas-vnir-spectra")).not.toContainText(
      /UNCOVERED/,
    );
  });

  test("shows an explicit UNCOVERED row when no instrument has the capability (AC-02)", async ({
    page,
  }) => {
    await startNeo(page);
    await page.getByTestId("objective-obj-thermal").getByRole("checkbox").check();
    const status = page.getByTestId("trace-status-meas-thermal-ir");
    await expect(status).toContainText("UNCOVERED");
    await expect(page.getByTestId("trace-row-meas-thermal-ir")).toContainText(
      /no selected instrument/i,
    );
    await expect(page.getByTestId("trace-row-meas-thermal-ir")).toContainText(
      /capability match/i,
    );
  });

  test("a failed analysis is reported with a retry, not silently ignored", async ({ page }) => {
    await page.route("**/api/mission/validate", (route) => route.abort());
    await startNeo(page);
    await expect(page.getByTestId("analysis-error")).toBeVisible();
    await expect(
      page.getByTestId("analysis-error").getByRole("button", { name: /retry/i }),
    ).toBeVisible();
    await expect(page.getByTestId("trace-row-meas-shape-model")).toContainText(
      /capability matched/i,
    );
  });
});

test.describe("workspace mission switching", () => {
  test("mission A -> mission B -> back to A shows the right mission each time", async ({
    page,
  }) => {
    const a = await startNeo(page);
    await page.getByTestId("objective-obj-thermal").getByRole("checkbox").check();
    await expect(page.getByTestId("revision-pill")).toHaveText("Revision 1");

    // Client-side navigation keeps the store (and the mounted workspace chrome) alive.
    await page.locator('header a[href="/"]').first().click();
    await page.getByTestId(NEO).getByRole("button", { name: /start mission/i }).click();
    await page.waitForURL(/\/mission\/mission-[0-9a-f]{12}$/);
    const b = new URL(page.url()).pathname.split("/").pop() as string;
    expect(b).not.toBe(a);
    await expect(page.getByTestId("workspace-mission-id")).toContainText(b);
    await expect(page.getByTestId("revision-pill")).toHaveText("Revision 0");
    await expect(page.getByTestId("objective-selected-count")).toHaveText(/2 of 3/);

    await page.goBack(); // landing
    await page.goBack(); // mission A (client-side history)
    await expect(page).toHaveURL(new RegExp(`/mission/${a}$`));
    await expect(page.getByTestId("workspace-mission-id")).toContainText(a);
    await expect(page.getByTestId("revision-pill")).toHaveText("Revision 1");
    await expect(page.getByTestId("objective-selected-count")).toHaveText(/3 of 3/);

    await page.goForward();
    await page.goForward();
    await expect(page.getByTestId("workspace-mission-id")).toContainText(b);
    await expect(page.getByTestId("objective-selected-count")).toHaveText(/2 of 3/);
  });
});

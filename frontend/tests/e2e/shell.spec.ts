import { expect, test, type Page } from "@playwright/test";

const NEO = "scenario-card-neo-rendezvous";

async function startNeo(page: Page): Promise<string> {
  await page.goto("/");
  const card = page.getByTestId(NEO);
  await card.getByRole("button", { name: /start mission/i }).click();
  await page.waitForURL(/\/mission\/mission-[0-9a-f]{12}$/);
  return new URL(page.url()).pathname.split("/").pop() as string;
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
}

test.describe("landing", () => {
  test("shows three scenario cards, all playable (Task 7.1)", async ({ page }) => {
    await page.goto("/");
    const cards = page.locator('[data-testid^="scenario-card-"]');
    await expect(cards).toHaveCount(3);
    for (const id of ["neo-rendezvous", "lunar-polar-scout", "earth-observation"]) {
      const card = page.getByTestId(`scenario-card-${id}`);
      await expect(card.getByRole("button", { name: /start mission/i })).toBeEnabled();
      await expect(card.getByText("Preview", { exact: true })).toHaveCount(0);
    }
  });

  test("starting NEO saves the mission and opens the brief", async ({ page }) => {
    const id = await startNeo(page);
    await expect(page.getByTestId("workspace-title")).toBeVisible();
    const stored = await page.evaluate(
      (key) => window.localStorage.getItem(key),
      `missionforge:mission:${id}`,
    );
    expect(stored).toContain(id);
  });

  test("shows an offline banner with retry when the backend is unreachable", async ({
    page,
  }) => {
    await page.route("**/api/health", (route) => route.abort());
    await page.route("**/api/templates", (route) => route.abort());
    await page.goto("/");
    await expect(page.getByTestId("offline-banner")).toContainText(
      /backend (is )?unreachable/i,
    );
    await expect(
      page.getByTestId("offline-banner").getByRole("button", { name: /retry/i }),
    ).toBeVisible();
    await expect(
      page.getByTestId("error-state").getByRole("button", { name: /retry/i }),
    ).toBeVisible();
    await expect(
      page.getByText("independent educational prototype").first(),
    ).toBeVisible();
  });
});

test.describe("workspace routing", () => {
  test("direct /architect/<id> after refresh restores the mission", async ({ page }) => {
    const id = await startNeo(page);
    const title = (await page.getByTestId("workspace-title").textContent()) ?? "";
    expect(title.length).toBeGreaterThan(0);

    await page.goto(`/architect/${id}`);
    await expect(page.getByTestId("workspace-title")).toHaveText(title);
    await page.reload();
    await expect(page.getByTestId("workspace-title")).toHaveText(title);
    await expect(page.getByTestId("workspace-mission-id")).toContainText(id);
  });

  test("unknown mission id shows not-found with a Start a mission action", async ({
    page,
  }) => {
    await page.goto("/architect/mission-doesnotexist");
    await expect(page.getByRole("heading", { name: /mission not found/i })).toBeVisible();
    await page.getByRole("link", { name: /start a mission/i }).click();
    await expect(page).toHaveURL("/");
  });

  test("malformed mission id is treated as not found", async ({ page }) => {
    await page.goto("/mission/%3Cb%3Ex");
    await expect(page.getByRole("heading", { name: /mission not found/i })).toBeVisible();
  });

  test("corrupt stored mission is reported without crashing", async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("missionforge:mission:mission-corrupt0001", "{not json");
    });
    await page.goto("/mission/mission-corrupt0001");
    await expect(page.getByTestId("not-found-state")).toContainText(/could not be read/i);
    await expect(page.getByRole("link", { name: /start a mission/i })).toBeVisible();
  });

  test("structurally partial stored mission is treated as corrupt, not a crash", async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.addInitScript(() => {
      window.localStorage.setItem(
        "missionforge:mission:mission-partial0001",
        JSON.stringify({
          schemaVersion: "1.0",
          missionId: "mission-partial0001",
          designRevision: 0,
          scenarioId: "neo-rendezvous",
          title: "Partial",
          architecture: {},
        }),
      );
    });
    await page.goto("/architect/mission-partial0001");
    await expect(page.getByTestId("not-found-state")).toContainText(/could not be read/i);
    expect(errors).toEqual([]);
  });

  test("blocked or full storage does not break starting a mission", async ({ page }) => {
    await page.addInitScript(() => {
      Storage.prototype.setItem = () => {
        throw new DOMException("quota", "QuotaExceededError");
      };
    });
    await startNeo(page);
    await expect(page.getByTestId("workspace-title")).toBeVisible();
    await expect(page.getByTestId("save-status")).toContainText(/not saved/i);
  });

  test("arena placeholder loads for a saved mission; run routes are not found", async ({
    page,
  }) => {
    const id = await startNeo(page);
    await page.goto(`/arena/${id}`);
    await expect(page.getByTestId("workspace-title")).toBeVisible();
    await expect(page.getByRole("navigation", { name: /mission workspace/i })).toBeVisible();

    await page.goto("/control/run-unknown");
    await expect(page.getByRole("heading", { name: /run not found/i })).toBeVisible();
    await page.goto("/review/run-unknown");
    await expect(page.getByRole("heading", { name: /run not found/i })).toBeVisible();
  });

  test("disclaimer is present on every page", async ({ page }) => {
    const id = await startNeo(page);
    for (const path of ["/", `/mission/${id}`, `/architect/${id}`, "/about", "/nope-nope"]) {
      await page.goto(path);
      await expect(page.getByRole("contentinfo")).toContainText(
        "independent educational prototype",
      );
    }
  });
});

test.describe("375px layout", () => {
  test.use({ viewport: { width: 375, height: 812 } });

  test("no horizontal overflow on landing, workspace and about", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator('[data-testid^="scenario-card-"]')).toHaveCount(3);
    await expectNoHorizontalOverflow(page);

    const id = await startNeo(page);
    await expect(page.getByTestId("workspace-title")).toBeVisible();
    await expectNoHorizontalOverflow(page);
    await page.goto(`/architect/${id}`);
    await expect(page.getByTestId("workspace-title")).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await page.goto("/about");
    await expectNoHorizontalOverflow(page);
  });
});

test.describe("status components (legend on /about)", () => {
  const constraintStates = [
    ["pass", "Pass"],
    ["warning", "Watch"],
    ["fail", "Fail"],
    ["not-modelled", "Not modelled"],
  ] as const;

  for (const [status, text] of constraintStates) {
    test(`ConstraintBadge ${status} renders icon and text`, async ({ page }) => {
      await page.goto("/about");
      const badge = page.getByTestId(`constraint-badge-${status}`);
      await expect(badge).toContainText(text);
      await expect(badge.locator("svg")).toHaveCount(1);
    });
  }

  const fidelities = [
    ["source-backed", "Source-backed"],
    ["derived", "Derived"],
    ["gameplay-estimate", "Gameplay estimate"],
    ["not-modelled", "Not modelled"],
  ] as const;

  for (const [fidelity, text] of fidelities) {
    test(`FidelityBadge ${fidelity} renders icon and text`, async ({ page }) => {
      await page.goto("/about");
      const badge = page.getByTestId(`fidelity-badge-${fidelity}`);
      await expect(badge).toContainText(text);
      await expect(badge.locator("svg")).toHaveCount(1);
    });
  }

  test("ProvenancePopover opens and closes by keyboard", async ({ page }) => {
    await page.goto("/about");
    const trigger = page.getByRole("button", { name: /show provenance/i }).first();
    await trigger.focus();
    await page.keyboard.press("Enter");
    const panel = page.getByTestId("provenance-panel");
    await expect(panel).toBeVisible();
    await expect(panel).toContainText("Source");
    await expect(panel).toContainText("Assumptions");
    await page.keyboard.press("Escape");
    await expect(panel).toBeHidden();
    await expect(trigger).toBeFocused();
  });
});

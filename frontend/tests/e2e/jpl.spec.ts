import { expect, test } from "@playwright/test";

/** Phase 5 (AC-08, AC-09, architecture 10 / 12.7): JPL data only through the backend. */

test("target picker: backend-only requests, honest offline badge, trajectory written", async ({ page }) => {
  const hosts = new Set<string>();
  page.on("request", (r) => hosts.add(new URL(r.url()).host));

  await page.goto("/");
  await page.getByTestId("scenario-card-neo-rendezvous").getByRole("button", { name: /start mission/i }).click();
  await page.waitForURL(/\/mission\/mission-[0-9a-f]{12}$/);
  const id = new URL(page.url()).pathname.split("/").pop() as string;

  const picker = page.getByTestId("target-picker");
  const badge = page.getByTestId("jpl-source-badge");
  await expect(badge).toBeVisible({ timeout: 30_000 });
  // e2e runs the backend offline: the bundled snapshot, never "LIVE"
  await expect(badge).toHaveText(/^(SYNTHETIC — not JPL data|DEMO — captured .+)$/);
  await expect(badge).not.toContainText("LIVE");

  const row = picker.locator("[data-testid^='target-option-']").nth(1);
  await row.getByRole("button", { name: /use this target/i }).click();
  await expect(row).toContainText(/in use/i);

  const stored = await page.evaluate((key) => JSON.parse(window.localStorage.getItem(key) ?? "null"), `missionforge:mission:${id}`);
  expect(stored.trajectory.provider).toBe("jpl-mdesign");
  expect(stored.trajectory.rawSourceRef).toMatch(/^jpl-mdesign:[0-9a-f]{24}$/);
  expect(stored.destination.bodyType).toBe("asteroid");

  // the engine keeps C3 as launch energy: spacecraft delta-v is the scenario burn
  const res = await page.request.post("http://127.0.0.1:8000/api/mission/validate", { data: { missionState: stored } });
  const analysis = (await res.json()).data.analysis;
  expect(analysis.budgets.requiredDeltaVKmPerS.value).toBeCloseTo(0.25, 6);

  await page.goto(`/architect/${id}`);
  await expect(page.getByTestId("analysis-revision")).toBeVisible({ timeout: 30_000 });

  for (const host of hosts) {
    expect(["localhost:3000", "127.0.0.1:8000"]).toContain(host);
  }
  expect([...hosts].some((h) => h.includes("jpl.nasa.gov"))).toBe(false);
});

test("health reports the JPL adapter as demo when running offline", async ({ page }) => {
  const res = await page.request.get("http://127.0.0.1:8000/api/health");
  expect((await res.json()).data.jplAdapter.status).toBe("demo");
});

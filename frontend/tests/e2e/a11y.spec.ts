import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

/** Task 7.4: axe-core on every route, 0 serious or critical violations (desktop + 375 px). */

async function seriousViolations(page: Page): Promise<string[]> {
  const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  return result.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(" ")).slice(0, 4).join(" | ")}`);
}

async function journey(page: Page): Promise<{ missionId: string; runId: string }> {
  await page.goto("/");
  await page.getByTestId("scenario-card-neo-rendezvous").getByRole("button", { name: /start mission/i }).click();
  await page.waitForURL(/\/mission\/mission-[0-9a-f]{12}$/);
  const missionId = new URL(page.url()).pathname.split("/").pop() as string;
  await page.goto(`/architect/${missionId}`);
  await expect(page.getByTestId("analysis-revision")).toContainText(/revision 0/i, { timeout: 30_000 });
  await page.getByTestId("category-nav-communications").click();
  await page.getByTestId("select-comms-xband-medium").click();
  await page.getByTestId("confirm-change").click();
  await expect(page.getByTestId("mission-ready-badge")).toHaveText(/^mission-ready$/i);
  await page.getByTestId("launch-button").click();
  await page.waitForURL(/\/control\/[^/]+/, { timeout: 30_000 });
  const runId = new URL(page.url()).pathname.split("/").pop() as string;
  return { missionId, runId };
}

for (const width of [1280, 375]) {
  test(`no serious axe violations on any route at ${width} px`, async ({ page }) => {
    test.setTimeout(180_000);
    await page.setViewportSize({ width, height: 900 });
    const { missionId, runId } = await journey(page);
    const routes: [string, string][] = [
      ["/", "scenario-card-neo-rendezvous"],
      ["/about", ""],
      [`/mission/${missionId}`, "workspace-title"],
      [`/architect/${missionId}`, "analysis-revision"],
      [`/arena/${missionId}`, ""],
      [`/control/${runId}`, "mission-control"],
      [`/review/${runId}`, "review-outcome"],
    ];
    const failures: string[] = [];
    for (const [path, ready] of routes) {
      await page.goto(path);
      // phone-width architect shows one zone at a time: wait for the analysis to arrive, visible or not
      if (ready) await expect(page.getByTestId(ready).first()).toBeAttached({ timeout: 30_000 });
      if (ready === "analysis-revision") await expect(page.getByTestId(ready).first()).toContainText(/revision/i, { timeout: 30_000 });
      await page.waitForLoadState("networkidle");
      for (const v of await seriousViolations(page)) failures.push(`${path}: ${v}`);
    }
    expect(failures, failures.join("\n")).toEqual([]);
  });
}

test("/about explains fidelity tiers, sources, credits and non-endorsement", async ({ page }) => {
  await page.goto("/about");
  for (const heading of [
    "What each fidelity level means",
    "What is modelled, and what is not claimed",
    "Sources and references",
    "Credits and endorsement",
  ]) {
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
  }
  await expect(page.getByTestId("about-non-endorsement")).toContainText(/not endorsed by/i);
  await expect(page.getByRole("link", { name: /ssd-api\.jpl\.nasa\.gov/ })).toBeVisible();
  await expect(page.locator("img[src*='nasa' i], img[alt*='nasa logo' i]")).toHaveCount(0);
});

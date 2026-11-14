import { expect, test, type Page } from "@playwright/test";

/** Task 7.3: concept cards, prediction prompt, pre/post check; all optional and local. */

async function architect(page: Page): Promise<string> {
  await page.goto("/");
  await page.getByTestId("scenario-card-neo-rendezvous").getByRole("button", { name: /start mission/i }).click();
  await page.waitForURL(/\/mission\/mission-[0-9a-f]{12}$/);
  const id = new URL(page.url()).pathname.split("/").pop() as string;
  await page.goto(`/architect/${id}`);
  await expect(page.getByTestId("analysis-revision")).toContainText(/revision 0/i, { timeout: 30_000 });
  return id;
}

test("concept cards appear where the idea first matters and stay dismissed", async ({ page }) => {
  await architect(page);
  await expect(page.getByTestId("concept-card-lo2")).toBeVisible();
  await page.getByTestId("category-nav-power").click();
  await expect(page.getByTestId("concept-card-lo3")).toContainText(/watt-hours/i);
  await page.getByTestId("category-nav-propulsion").click();
  await expect(page.getByTestId("concept-card-lo4")).toContainText(/C3/);
  await page.getByTestId("concept-card-lo4").getByRole("button", { name: /dismiss/i }).click();
  await expect(page.getByTestId("concept-card-lo4")).toHaveCount(0);
  await page.reload();
  await page.getByTestId("category-nav-propulsion").click();
  await expect(page.getByTestId("concept-card-lo4")).toHaveCount(0);
});

test("first mission completes with hints and prediction, no blocking dialog", async ({ page }) => {
  const missionId = await architect(page);
  await page.getByTestId("prediction-prompt").getByLabel(/over three quarters/i).check();
  await page.getByTestId("category-nav-communications").click();
  await page.getByTestId("select-comms-xband-medium").click();
  await expect(page.getByTestId("mission-ready-badge")).toHaveText(/^mission-ready$/i);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByTestId("launch-button").click();
  await page.waitForURL(/\/control\/[^/]+/, { timeout: 30_000 });
  await expect(page.getByTestId("concept-card-lo7")).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const runId = new URL(page.url()).pathname.split("/").pop() as string;
  await page.goto(`/review/${runId}`);
  await expect(page.getByTestId("concept-card-lo5")).toBeVisible();
  await expect(page.getByTestId("concept-card-lo6")).toBeVisible();
  await expect(page.getByTestId("prediction-result")).toContainText(/you predicted .over three quarters/i);
  expect(missionId).toBeTruthy();
});

test("pre-check on landing, post-check on review compares scores; stored locally only", async ({ page }) => {
  const sent: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST") sent.push(r.postData() ?? "");
  });
  await page.goto("/");
  await page.getByTestId("learning-pre-start").click();
  const pre = page.getByTestId("learning-check-pre");
  for (const name of ["pre-q-energy", "pre-q-c3", "pre-q-return"]) {
    await pre.locator(`input[name='${name}']`).first().check(); // first option: wrong answers
  }
  await page.getByTestId("learning-pre-submit").click();
  await expect(page.getByTestId("learning-pre-score")).toContainText("0 of 3");

  const id = await architect(page);
  await page.getByTestId("category-nav-communications").click();
  await page.getByTestId("select-comms-xband-medium").click();
  await expect(page.getByTestId("mission-ready-badge")).toHaveText(/^mission-ready$/i);
  await page.getByTestId("launch-button").click();
  await page.waitForURL(/\/control\/[^/]+/, { timeout: 30_000 });
  const runId = new URL(page.url()).pathname.split("/").pop() as string;
  await page.goto(`/review/${runId}`);
  await page.getByTestId("learning-post-start").click();
  const post = page.getByTestId("learning-check-post");
  for (const name of ["post-q-energy", "post-q-c3", "post-q-return"]) {
    await post.locator(`input[name='${name}']`).nth(1).check(); // second option: correct
  }
  await page.getByTestId("learning-post-submit").click();
  await expect(page.getByTestId("learning-post-score")).toContainText("3 of 3");
  await expect(page.getByTestId("learning-post-score")).toContainText("Before playing: 0 of 3");
  expect(sent.some((b) => b.includes("q-energy"))).toBe(false); // answers never leave the browser
  expect(id).toBeTruthy();
});

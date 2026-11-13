import { expect, test } from "@playwright/test";

test("landing page shows brand, disclaimer and backend engine status", async ({
  page,
}) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { level: 1, name: "MISSIONFORGE" }),
  ).toBeVisible();

  await expect(
    page.getByText("independent educational prototype").first(),
  ).toBeVisible();

  await expect(page.getByTestId("backend-status")).toContainText(
    "Engine 0.1.0",
  );
});

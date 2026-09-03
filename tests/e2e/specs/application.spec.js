import { expect, test } from "@playwright/test";


test("opens the CRM frontend", async ({ page }) => {
  await page.goto("/");

  await expect(page).toHaveTitle("Volunteer CRM");
  await expect(page.getByRole("heading", { name: "Volunteer CRM" })).toBeVisible();
});

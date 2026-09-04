import { expect, test } from "@playwright/test";


test("offers social sign-in when there is no CRM session", async ({ page }) => {
  await page.goto("/");

  await expect(page).toHaveTitle("Volunteer CRM");
  await expect(page.getByRole("heading", { name: "Volunteer CRM" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Continue with Google" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Continue with Microsoft" })).toBeVisible();
});

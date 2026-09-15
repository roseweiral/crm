/**
 * Documentation browser — see web/README.md "Documentation (/documents,
 * /documents/:id)" for the documented states and behavior these specs are
 * written from.
 */
import { expect, test } from "./support/fixtures";

test("requires a session", async ({ page }) => {
  await page.goto("/documents");

  await expect(page.getByRole("heading", { name: "Volunteer CRM" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Continue with Google" })).toBeVisible();
});

test("shows the sidebar grouped by category with no document selected", async ({
  person,
  signedInContext,
}) => {
  const { account } = await person();
  const context = await signedInContext(account.id);
  const page = await context.newPage();

  await page.goto("/documents");

  await expect(page.getByRole("link", { name: "Way of working" })).toBeVisible();
  await expect(page.getByText("Select a document to read it.")).toBeVisible();
});

test("opens a document and renders its content", async ({ person, signedInContext }) => {
  const { account } = await person();
  const context = await signedInContext(account.id);
  const page = await context.newPage();

  await page.goto("/documents");
  await page.getByRole("link", { name: "Way of working" }).click();

  await expect(page).toHaveURL(/\/documents\/way-of-working$/);
  await expect(page.getByRole("heading", { level: 1, name: "Way of working" })).toBeVisible();
  await expect(page.getByText("Agree the deliverable").first()).toBeVisible();
});

test("shows a not-found message for an unknown document id", async ({
  person,
  signedInContext,
}) => {
  const { account } = await person();
  const context = await signedInContext(account.id);
  const page = await context.newPage();

  await page.goto("/documents/does-not-exist");

  await expect(page.getByText("This document doesn't exist.")).toBeVisible();
});

test("clicking a cross-link navigates in-app to the linked document", async ({
  person,
  signedInContext,
}) => {
  const { account } = await person();
  const context = await signedInContext(account.id);
  const page = await context.newPage();

  await page.goto("/documents/way-of-working");

  // way-of-working.md's "Before starting: check open questions" section
  // links to open-questions.md — a real cross-link already in the content,
  // not something added for this test.
  await page.getByRole("link", { name: "open-questions.md" }).first().click();

  await expect(page).toHaveURL(/\/documents\/open-questions$/);
  await expect(page.getByRole("heading", { level: 1, name: "Open questions" })).toBeVisible();
});

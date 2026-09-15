/**
 * Address Book screen — see web/README.md "Address Book (/address-book)"
 * for the documented states and behavior these specs are written from.
 */
import { randomUUID } from "node:crypto";

import { expect, roleTypeId, test } from "./support/fixtures";

test("requires a session", async ({ page }) => {
  await page.goto("/address-book");

  await expect(page.getByRole("heading", { name: "Volunteer CRM" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Continue with Google" })).toBeVisible();
});

test("shows a permission-denied message for a contact with no eligible role", async ({
  person,
  signedInContext,
}) => {
  const { account } = await person();
  const context = await signedInContext(account.id);
  const page = await context.newPage();

  await page.goto("/address-book");

  await expect(
    page.getByText(
      "You need an active Group Leader, Group Helper, Area Manager, or System Administrator role to browse the address book.",
    ),
  ).toBeVisible();
});

test("lists an eligible volunteer and links to visibility settings", async ({
  records,
  person,
  signedInContext,
}) => {
  const groupType = await records("group_types", { name: `E2E group type ${randomUUID()}` });
  const group = await records("groups", { group_type_id: groupType.id, name: `E2E group ${randomUUID()}` });
  const { contact, account } = await person();
  await records("contact_roles_groups", {
    contact_id: contact.id,
    role_type_id: await roleTypeId("Group Leader"),
    group_id: group.id,
    start_date: new Date().toISOString().slice(0, 10),
  });

  const context = await signedInContext(account.id);
  const page = await context.newPage();
  await page.goto("/address-book");

  // Filter to this test's own fresh group so the assertion is deterministic
  // regardless of how many other eligible people already exist (seed data,
  // or other specs running in parallel) and which page they'd otherwise
  // land on.
  await page.getByLabel(/organisation structure|filter by group/i).selectOption({ label: group.name as string });

  await expect(page.locator(".results").getByText(`${contact.first_name} ${contact.last_name}`)).toBeVisible();
  await expect(page.getByRole("link", { name: "Manage my visibility" })).toBeVisible();
});

test("group filter restricts results to the selected branch", async ({
  records,
  person,
  signedInContext,
}) => {
  const groupLeaderRoleTypeId = await roleTypeId("Group Leader");

  const branchAType = await records("group_types", { name: `E2E branch A type ${randomUUID()}` });
  const branchA = await records("groups", {
    group_type_id: branchAType.id,
    name: `E2E branch A ${randomUUID()}`,
  });
  const branchBType = await records("group_types", { name: `E2E branch B type ${randomUUID()}` });
  const branchB = await records("groups", {
    group_type_id: branchBType.id,
    name: `E2E branch B ${randomUUID()}`,
  });

  const { contact: inBranchA, account: viewerAccount } = await person();
  await records("contact_roles_groups", {
    contact_id: inBranchA.id,
    role_type_id: groupLeaderRoleTypeId,
    group_id: branchA.id,
    start_date: new Date().toISOString().slice(0, 10),
  });

  const { contact: inBranchB } = await person();
  await records("contact_roles_groups", {
    contact_id: inBranchB.id,
    role_type_id: groupLeaderRoleTypeId,
    group_id: branchB.id,
    start_date: new Date().toISOString().slice(0, 10),
  });

  const context = await signedInContext(viewerAccount.id);
  const page = await context.newPage();
  await page.goto("/address-book");

  await page.getByLabel(/organisation structure|filter by group/i).selectOption({ label: branchA.name as string });

  await expect(page.locator(".results").getByText(`${inBranchA.first_name} ${inBranchA.last_name}`)).toBeVisible();
  await expect(page.locator(".results")).not.toContainText(`${inBranchB.first_name} ${inBranchB.last_name}`);
});

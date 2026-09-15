/**
 * My directory visibility screen — see web/README.md
 * "My directory visibility (/address-book/visibility)" for the documented
 * states and behavior these specs are written from.
 */
import { randomUUID } from "node:crypto";

import { expect, roleTypeId, test } from "./support/fixtures";

test("requires a session", async ({ page }) => {
  await page.goto("/address-book/visibility");

  await expect(page.getByRole("heading", { name: "Volunteer CRM" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Continue with Google" })).toBeVisible();
});

test("is available even without an eligible role", async ({ person, signedInContext }) => {
  const { account } = await person();
  const context = await signedInContext(account.id);
  const page = await context.newPage();

  await page.goto("/address-book/visibility");

  await expect(
    page.getByText(
      "You don't currently hold a role that appears in the address book. These settings will apply if you do.",
    ),
  ).toBeVisible();
  await expect(
    page.getByLabel("Hide my profile from the address book entirely"),
  ).toBeVisible();
});

test("hiding my whole profile removes me from another eligible viewer's address book", async ({
  records,
  person,
  signedInContext,
}) => {
  const groupLeaderRoleTypeId = await roleTypeId("Group Leader");

  const selfGroupType = await records("group_types", { name: `E2E self type ${randomUUID()}` });
  const selfGroup = await records("groups", {
    group_type_id: selfGroupType.id,
    name: `E2E self group ${randomUUID()}`,
  });
  const { contact: self, account: selfAccount } = await person();
  await records("contact_roles_groups", {
    contact_id: self.id,
    role_type_id: groupLeaderRoleTypeId,
    group_id: selfGroup.id,
    start_date: new Date().toISOString().slice(0, 10),
  });

  const viewerGroupType = await records("group_types", { name: `E2E viewer type ${randomUUID()}` });
  const viewerGroup = await records("groups", {
    group_type_id: viewerGroupType.id,
    name: `E2E viewer group ${randomUUID()}`,
  });
  const { contact: viewer, account: viewerAccount } = await person();
  await records("contact_roles_groups", {
    contact_id: viewer.id,
    role_type_id: groupLeaderRoleTypeId,
    group_id: viewerGroup.id,
    start_date: new Date().toISOString().slice(0, 10),
  });

  const selfContext = await signedInContext(selfAccount.id);
  const selfPage = await selfContext.newPage();
  await selfPage.goto("/address-book/visibility");
  await selfPage.getByLabel("Hide my profile from the address book entirely").check();
  await selfPage.getByRole("button", { name: "Save changes" }).click();
  await expect(selfPage.getByText(/saved|updated/i)).toBeVisible();

  // Self is now hidden, so their now-empty group can no longer surface as a
  // filter *option* (nobody eligible is left in it to derive it from) — see
  // AddressBookPage's group-options comment. Navigate straight to the
  // filtered URL instead, which the page supports as a shareable link
  // regardless of whether the select currently offers that option; this is
  // what actually proves the hide took effect, as opposed to re-testing
  // filter-option discovery, which the other specs already cover.
  const viewerContext = await signedInContext(viewerAccount.id);
  const viewerPage = await viewerContext.newPage();
  await viewerPage.goto(`/address-book?group=${selfGroup.id}`);

  await expect(viewerPage.locator(".results")).toHaveCount(0);
  await expect(viewerPage.getByText("No one matches this filter yet.")).toBeVisible();
});

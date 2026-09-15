/**
 * Generic API browser's Contacts detail view — see web/README.md
 * "Generic API browser (/resources)" for the documented behavior this
 * spec is written from: opening a contact fetches the profile aggregate
 * (GET /api/v1/contacts/{id}/profile), so phone numbers, addresses, and
 * emergency contacts (with the referenced person's own name/phone/email
 * embedded, not just their GUID) appear alongside the contact's own
 * fields.
 */
import { randomUUID } from "node:crypto";

import { expect, test } from "./support/fixtures";

test("shows a contact's phone number, address, and emergency contact in the resource browser", async ({
  records,
  signedInContext,
}) => {
  // Built directly with records() rather than person(), which hard-codes
  // first_name "E2E" and a UUID last_name - "0" sorts before every real
  // seeded name (ORDER BY last_name, first_name, id) so this contact lands
  // on the list's first page regardless of how much demo data exists.
  const marker = randomUUID();
  const contact = await records("contacts", {
    first_name: `0E2E-${marker}`,
    last_name: `0E2E-${marker}`,
    email: `${marker}@example.test`,
    can_login: true,
  });
  const account = await records("user_accounts", { contact_id: contact.id, status: "active" });
  await records("contact_phone_numbers", {
    contact_id: contact.id,
    phone_type: "mobile",
    number: "07700 900123",
    is_primary: true,
    start_date: new Date().toISOString().slice(0, 10),
  });
  await records("contact_addresses", {
    contact_id: contact.id,
    address_type: "home",
    line1: "1 Test Street",
    start_date: new Date().toISOString().slice(0, 10),
  });

  const emergencyContact = await records("contacts", {
    first_name: "Priya",
    last_name: `E2ERelative-${marker}`,
    email: `priya-${marker}@example.test`,
    can_login: false,
  });
  await records("contact_phone_numbers", {
    contact_id: emergencyContact.id,
    phone_type: "mobile",
    number: "07700 900456",
    is_primary: true,
    start_date: new Date().toISOString().slice(0, 10),
  });
  await records("contact_emergency_contacts", {
    contact_id: contact.id,
    emergency_contact_id: emergencyContact.id,
    priority: 1,
    relationship: "Mother",
  });

  const context = await signedInContext(account.id);
  const page = await context.newPage();
  await page.goto("/resources");

  await page.getByRole("button", { name: "Get Contacts" }).click();
  await page
    .getByRole("button", { name: new RegExp(`0E2E-${marker}`) })
    .click();

  await expect(page.getByText("07700 900123")).toBeVisible();
  await expect(page.getByText("1 Test Street")).toBeVisible();
  await expect(page.getByText(`E2ERelative-${marker}`)).toBeVisible();
  await expect(page.getByText("07700 900456")).toBeVisible();
});

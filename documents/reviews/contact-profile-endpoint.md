# Contact profile (read-only aggregate) review

## Delivered scope

`GET /api/v1/contacts/{contact_id}/profile` — bundles a contact's core
fields, current phone numbers, current addresses, and (when permitted)
emergency contacts into one response, for the frontend's contact details
page. Triggered by the user reporting addresses weren't visible on the
page where they expected them; the underlying question — should
`GET /contacts/{id}` itself just return everything — was resolved with the
user first, since embedding related, independently-changing data into
`ContactDetail` would have made its `PATCH`-driving ETag change for
reasons unrelated to what a caller actually edited. The user chose a
separate, unversioned, read-only aggregate endpoint instead.

Authorization: `contact` and the two current-only lists (`phone_numbers`,
`addresses`) are gated by `contact:view`, unchanged, exactly like
`GET /contacts/{id}` and the phone/address collection endpoints already
are. `emergency_contacts` is gated separately by `contact:view-sensitive`
and is `null` (not `[]`) when the caller lacks it — `[]` means "recorded
as having none," `null` means "you can't see this." Contract:
`documents/api-contract.md` "Contact profile (read-only aggregate)".
Executable coverage: `tests/api/test_contact_profile.py` (8 cases).

## TDD evidence

- All 8 cases confirmed red before implementation - some via missing
  route (404 instead of 401), some via a genuine test-authoring bug
  caught during the same red pass (see below).
- First implementation pass (the `ContactProfile` model reusing
  `ContactPhoneNumber`/`ContactAddress`/`ContactEmergencyContact` directly
  from their existing modules, and the aggregate endpoint) landed all 8
  green immediately once the test bug was fixed - no implementation bug
  found in this endpoint itself.
- Full suite: 308 collected, 251 contract-marked passing (up from 243),
  54 regression passing - both on a fresh database and repeated without a
  reset.

## Issues found and fixed

- **Test bug: end-dating a just-created row with a past date violates the
  table's own date-ordering constraint.** Two setup steps in
  `test_profile_includes_only_current_phone_numbers_and_addresses` tried
  to retire a freshly-created phone number/address by patching
  `end_date` to yesterday - but `start_date` defaults to *today*, and
  `chk_contact_phone_numbers_dates`/`chk_contact_addresses_dates` both
  require `end_date >= start_date`. Caught immediately as a `psycopg
  CheckViolation` on the very first red run, before any assertion ran.
  Fixed by end-dating to today instead of yesterday - the test only needs
  a non-null `end_date` to prove "not current" filtering works; it
  doesn't need the row to be historically in the past.

## Design decisions made during implementation

- **`phone_numbers`/`addresses` are current-only** (`end_date IS NULL`),
  unlike their own collection endpoints which return full history. This
  aggregate is a "what do I need to know right now" view for a details
  page, not a history browser - the existing
  `GET /api/v1/contact-phone-numbers`/`contact-addresses` endpoints
  remain how historical rows are queried, unchanged.
- **No `ETag`, no pagination.** Confirmed explicitly in the contract:
  this endpoint is display-only (writes still go through each resource's
  own `PATCH`/`POST`/`DELETE` endpoint), and a contact's current phone
  numbers/addresses/emergency contacts are always a small, bounded set.
- **Reused the existing Pydantic response models directly**
  (`ContactPhoneNumber`, `ContactAddress`, `ContactEmergencyContact` -
  the base, non-`Detail` variants, since this view doesn't need
  `created_at`/`modified_at`) rather than defining parallel "summary"
  models, keeping the JSON shape for each nested item identical to what
  the collection endpoints already return.

## Deployment notes

No infrastructure or schema changes - reads only, no new tables.

## Follow-up: embedding the emergency contact's own details

Delivered after the initial review above, per direct user feedback:
returning only `emergency_contact_id` (a GUID) wasn't useful on its own -
the frontend would need a second request per entry to show who it
actually is. Each `emergency_contacts` entry now also embeds the
referenced contact's `first_name`, `last_name`, `email`, and
`phone_number` (that person's current primary number, falling back to
their most recently added current number, or `null` if they have none
recorded) via a `JOIN` plus a `LEFT JOIN LATERAL` in
`get_contact_profile`. New model: `ContactProfileEmergencyContact`
(distinct from the plain `ContactEmergencyContact` used by the
`contact-emergency-contacts` CRUD endpoints, which are unchanged -
embedding a joined person's details there wasn't asked for and isn't
needed for managing the link itself).

**Design decision made explicitly, not silently**: embedding this PII is
*not* gated by any further permission check against the referenced
contact's own record (e.g. the caller need not independently have
`contact:view` over the emergency contact themselves). Once a caller is
permitted to see *whose* emergency contact someone is
(`contact:view-sensitive` on the contact being viewed), withholding how
to reach that person would defeat the feature's entire purpose - the
existing `contact:view-sensitive` gate remains the meaningful boundary.
Documented in `documents/api-contract.md`.

3 new test cases (exact embedded shape, primary-number preference, still
`[]` not `null` when none recorded) plus the two existing tests updated
for the new field set. All 9 cases in `tests/api/test_contact_profile.py`
green; full suite: 309 collected, 252 contract-marked passing, 54
regression passing - fresh and repeated. No implementation bug found;
confirmed red only for the expected reason (missing fields).

No frontend code changes were needed - `RecordDetails`' existing generic,
recursive rendering picked up the new fields automatically. Extended
`tests/e2e/specs/contact-profile.spec.ts` with a second contact and an
emergency-contact link to prove it explicitly (asserting the referenced
person's name and phone number are visible, not just checking nothing
broke); full e2e suite (14 specs) still green.

## Frontend

No dedicated contact details page exists yet in the frontend - the user's
report ("I don't see the addresses on the contact details page") was
about the generic, disposable API browser's Contacts detail view (`/resources`
→ Contacts → a contact), the only place a contact's data is currently
shown. Rather than build a new page, the existing `ResourcePage`/
`RecordDetails` components - which already render nested objects and
arrays recursively - were pointed at the new aggregate:

- `ResourceDefinition` gained an optional `detailSuffix`; the "contacts"
  entry sets it to `"profile"`.
- `getDetail(path, id, suffix?)` now builds `{path}/{id}/{suffix}` when a
  suffix is given, and returns the looser `Record<string, unknown>`
  rather than `ApiRecord` (the profile bundle has no top-level `id` of
  its own - only list items need one).
- Every other resource (Family Units, Role Types, Group Types, Groups,
  Contact Role Groups) is unaffected - `detailSuffix` unset, same plain
  detail fetch as before.

`tests/e2e/specs/contact-profile.spec.ts` (1 case): creates a contact with
a phone number and address directly via `records()` (not `person()`,
which doesn't support name overrides), naming it so it sorts to the
list's first page regardless of how much demo data exists, then confirms
both values are visible after opening it in the resource browser. Passed
on the first run - no bug found in the wiring itself. Full e2e suite: 14
passed (up from 13).

Documented in `web/README.md`'s new "Generic API browser (`/resources`)"
section, including the one known rough edge inherited from `RecordDetails`
not existing: `emergency_contacts: null` (no permission) and `[]` (no
contacts) currently render identically ("None") in this generic viewer,
called out as something a purpose-built contact details page should
handle explicitly if this browser is ever replaced.

## Not in this increment

- Any other resource gaining a `/profile`-shaped aggregate.
- Including historical (end-dated) phone numbers or addresses.
- Medical conditions - noted in the contract as a future fourth key on
  this same endpoint, once that category ships.
- A purpose-built, polished contact details page - this increment reuses
  the existing generic/disposable browser rather than building one.

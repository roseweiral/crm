# Main Contact tracking review

## Delivered scope

`GET /api/v1/family-units/{id}` gains `is_main_contact` per member; new
`POST /api/v1/family-units/{id}/main-contact` changes who holds it,
admin-only for now. Contract: `documents/api-contract.md` "Main Contact
tracking". Design rationale:
`documents/contact-data-expansion-design.md` (Prerequisite 1). Executable
coverage: `tests/api/test_family_main_contact.py`, plus an updated
assertion in `tests/api/test_family_units_endpoints.py` for the new field.

## TDD evidence

- 14 cases written directly from the contract, confirmed red before
  implementation: 13 failed for clear reasons (missing table, missing
  route, missing response field); the 14th
  (`test_set_main_contact_rejects_an_unknown_family_unit`) passed at the
  red stage for the wrong reason — no route existed at all yet, so *any*
  request 404'd regardless of whether the family unit was real, not
  because the "family not found" business logic worked. Re-verified after
  implementation that it now exercises the real code path (a genuine
  family unit with a genuinely unknown `contact_id` in the same test suite
  passes for the right reason instead).
- Two issues surfaced while turning the suite green, both fixed before
  calling it done (see below).
- After fixes: 238 tests pass (181 contract, 54 regression, 3 smoke — up
  from 224), both on a fresh database and repeated without a reset.

## Issues found and fixed

1. **Shared test fixture didn't know about the new foreign key.** The
   `records` fixture's teardown (`tests/api/conftest.py`) already
   special-cases `user_accounts` to clean up rows other endpoints create as
   a side effect (sessions, identities, audit events) before deleting the
   account itself, precisely because plain reverse-creation-order deletion
   can't know about endpoint-created dependents. `contact_family_main_contacts`
   rows are created the same way (by the endpoint, not the fixture), and
   deleting a tracked `contacts` row without also clearing its
   `contact_family_main_contacts` rows hit a foreign-key violation during
   teardown. Fixed by adding the same "endpoint-created dependent" cleanup
   for `contacts`, mirroring the existing `user_accounts` case exactly. This
   is genuinely shared infrastructure — it will silently protect the next
   increment that adds a table referencing `contacts` from the same failure
   mode.
2. **Test bug, not an app bug**: the idempotency test asserted zero audit
   events existed after a no-op repeat call, when the correct assertion is
   that the count didn't *increase* — the first (real) call had already
   legitimately written one. Fixed to capture the count before the
   idempotent call and compare, rather than assuming zero.
3. **`SetMainContact` didn't match the established write-payload
   convention**: every other write model (`ContactPatch`,
   `DirectoryVisibilityPatch`, `RoleVisibilityPatch`) sets
   `model_config = ConfigDict(extra="forbid")` so an unexpected field in the
   request body is a loud 422 instead of a silently ignored typo. Caught in
   review, fixed before calling the increment done — no dedicated new test
   added for it, matching that this specific behavior isn't separately
   tested for any of the other three models it now matches either.

## Prioritized follow-up improvements

1. **`GET` does slightly more work than necessary on an unauthorized
   404.** Extracting `_family_unit_detail()` as a shared helper for both
   routes means `get_family_unit` now runs the full members-with-Main-Contact
   join before checking `family:view`, where the original code checked
   authorization before running that query. Not a security issue (still a
   clean 404, no data in the response) and not a hot path, but a small,
   avoidable efficiency regression from the refactor. Worth tightening if
   this endpoint ever becomes a hot path; not urgent today.
2. **No index on `contact_family_main_contacts.contact_id` alone** (only
   the partial unique index on `family_unit_id`). Not needed by anything
   this increment ships — both routes query by `family_unit_id` — but
   likely wanted once a future increment needs "which family is this
   contact the Main Contact of," the reverse lookup. Add it when that
   increment actually needs it, not preemptively.
3. **This deliberately doesn't touch `family:view`'s read scope**, even
   though `family-and-directory-design.md`'s original vision was "Main
   Contact is the sole gate to family CRM access." Today, any contact with
   a `parent` relationship row can still read their family via the
   existing rule, regardless of Main Contact status — tracking who holds
   Main Contact status is a prerequisite for that tightening, not the
   tightening itself. Matches this increment's contract, which says so
   explicitly under "Not in this increment."

## Deployment and operational limits

New table (`contact_family_main_contacts`) added directly to `schema.sql`
and `db.dbml` — no live database yet, so no migration, per
`way-of-working.md`. Only a Global System Administrator can change Main
Contact; nothing else changed about who can read family data. This is
Prerequisite 1 of 3 from `contact-data-expansion-design.md`; the
Group-Leader-exact-group write scope (Prerequisite 2) and its family
extension (Prerequisite 3) remain separate, not-yet-started increments.

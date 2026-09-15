# Personal details review

## Delivered scope

The second data category from `contact-data-expansion-design.md`, after
contact details (phone/address). Five new nullable columns directly on
`contacts` — `date_of_birth`, `preferred_name`, `phonetic_name`,
`pronouns`, `gender` — surfaced through the *existing* contact endpoints
(`GET /api/v1/contacts`, `GET /api/v1/contacts/{id}`, `PATCH
/api/v1/contacts/{id}`) rather than new ones, since the data lives on the
same row as the core identity fields.

Per this session's explicit decision (asked directly, since it was a
genuine fork not settled by precedent): **one endpoint, two independently
checked authorizations**, rather than a dedicated new endpoint (the shape
used for phone/address) or loosening `contact:update` itself. `PATCH
/api/v1/contacts/{id}` now branches on which fields the payload sets —
`contact:update` for any of `first_name`/`last_name`/`email`/`status`
(unchanged, still admin + Group-Leader-exact-group only, no self-write,
per `open-questions.md` #4), and the new `contact-personal:update` for any
of the five personal-detail fields (full write model: admin, self, the
family's current Main Contact, a Group Leader over their exact group and
its members' families). Both checks apply independently when a payload
mixes fields from both groups; either failing rejects the whole request
before anything is looked up or changed.

Contract: `documents/api-contract.md` "Personal details". Schema:
`documents/database/db.dbml`, `database/schema.sql`. Executable coverage:
`tests/api/test_contact_personal_details.py` (26 cases), plus updates to
`tests/api/test_contacts_endpoints.py` for the now-larger response shape.

## TDD evidence

- All 26 new cases, plus the two updated `test_contacts_endpoints.py`
  cases, confirmed red before implementation (`422`s from
  `extra="forbid"` rejecting the not-yet-defined fields, `KeyError`s and
  dict-mismatches from the response shape not yet including them).
- First implementation pass (schema columns, `ContactPatch`/`Contact`
  model fields, the field-group-split authorization check,
  `contact-personal:update` policy action) landed 24/26 green in the new
  file; 2 failed for a test-design reason, not an app bug — see below.
- After the fix: all 26 green. Full suite: 279 collected, 222
  contract-marked passing (up from 208), 54 regression passing — both on
  a fresh database and repeated without a reset.

## Issues found and fixed

- **Test bug: fetching an ETag the caller can't legitimately have.**
  `test_outsider_cannot_update_personal_details` and the `Group Helper`
  case of `test_area_manager_and_group_helper_cannot_update_personal_details`
  both used this file's `tag()` helper — a `GET` followed by asserting
  `200` — to obtain a real `If-Match` value *as the denied actor itself*.
  But an outsider (and a Group Helper, who has no `contact:view` rule at
  all) can't view the target either, so the `GET` correctly returned
  `404`, and the test failed on the setup step rather than the assertion
  it was written to make. `test_contact_writes.py` already established the
  right pattern for exactly this situation — a placeholder `If-Match:
  "placeholder"` value, since authorization is deliberately checked
  *before* `If-Match` validation, so the real request under test still
  gets the `403` it should. Fixed by switching both cases to that pattern.

## Design decisions made during implementation

- **`date_of_birth` must not be in the future.** Not stated in the design
  session, but agreed and written into the contract during this
  increment as a plausibility check worth having (a future DOB is never
  valid data), while stopping short of any deeper validation — no age
  floor, no format checks beyond what Pydantic's `date` type already
  enforces. Enforced by a `field_validator` on `ContactPatch`, returning
  `422` like any other Pydantic validation failure.
- **`email` and the five personal-detail fields can be explicitly
  `null`.** Extends the existing `ContactPatch` convention (previously
  only `email` could be nulled) to the new nullable columns, using the
  same `Optional`-typed-field pattern rather than the hidden-default
  trick reserved for fields that must never become null
  (`first_name`/`last_name`/`status`).
- **Personal-detail fields are not settable at contact creation.** `POST
  /api/v1/contacts` (`ContactCreate`) is unchanged; the five fields are
  only reachable via `PATCH` after a contact exists, matching this
  session's "trivial schema" framing of the category and avoiding scope
  creep into the creation flow.

## Deployment notes

No infrastructure changes. `schema.sql` gained five nullable columns on
the existing `contacts` table; applied automatically to a fresh database.
No migration path exists yet for already-running databases (unchanged
project-wide state).

## Not in this increment

- Any format/plausibility validation on `preferred_name`/`phonetic_name`/
  `pronouns`/`gender` beyond length and control-character exclusion —
  free text, matching every other free-text field in this system.
- Surfacing personal details in the address book or any other read
  surface beyond the contact endpoints themselves.

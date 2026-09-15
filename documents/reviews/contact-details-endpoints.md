# Contact details: phone numbers and addresses review

## Delivered scope

The first real data category from `contact-data-expansion-design.md`, on
top of its three now-delivered prerequisites (Main Contact tracking,
Group-Leader-exact-group write scope, its family extension). Two new,
independent resources sharing the same dated-history shape as
`contact_roles_groups` (`start_date`/`end_date`, no hard deletion):

- `contact_phone_numbers` — `phone_type`, `number`, `is_primary` (at most
  one current primary per contact, enforced by a partial unique index and
  applied atomically on both create and update).
- `contact_addresses` — `address_type` (defaults `home`), `line1`
  required, `line2`/`city`/`region`/`postcode`/`country` optional.

Full CRUD-minus-delete (`GET` list, `GET` detail, `POST`, `PATCH`) for
both, at `/api/v1/contact-phone-numbers` and `/api/v1/contact-addresses`.
Two new authorization actions, `contact-phone:update` and
`contact-address:update`, deliberately distinct from `contact:update`:
Global System Administrator, the contact themselves (`self`), the family's
current Main Contact (`main_contact_family` — Prerequisite 1's table), and
a Group Leader over their exact group and its members' families
(`group_and_family` — Prerequisite 3, reused unchanged). Reading reuses
`contact:view` directly, unmodified — already a superset of what these
write rules grant. Contract: `documents/api-contract.md` "Contact details:
phone numbers and addresses". Schema: `documents/database/db.dbml`,
`database/schema.sql`. Executable coverage: `tests/api/test_contact_details_endpoints.py`
(17 cases).

## TDD evidence

- All 17 cases confirmed red before implementation (404s/`KeyError`s from
  missing routes and tables).
- First implementation pass (schema, authorization source, router,
  models, `main.py` registration) landed 11/17 green; 6 failed with `403`
  or a `KeyError` following from a first `403` — see below.
- After the fix: 16/17 green; the last failure was a test bug (comparing
  a `UUID` object from `database_rows` against a JSON string) — fixed in
  the test, not the app.
- Final state: 265 collected, 208 contract-marked passing (up from 191),
  54 regression passing — both on a fresh database and repeated without a
  reset.

## Issues found and fixed

- **Missing Global System Administrator rule on both new actions.** Every
  other write action in this system (`contact:update`, `contact:create`,
  `invitation:create`, `family:manage-main-contact`) grants
  `access_role = "Global System Administrator"` scope `all`, but the
  contract's "Write-access model" subsection only enumerated the three
  non-admin sources (self, Main Contact, Group Leader) and didn't call
  this out explicitly. The first policy draft mirrored the contract text
  literally and omitted it, so every `admin_writer`-fixture test in
  `test_contact_details_endpoints.py` failed with `403` instead of `201`.
  Caught immediately by the red-to-green run against the full contract
  test file (6 of 17 failing on the first pass). Fixed by adding the rule
  to both actions in `app/policies/authorization.toml`, and by amending
  `api-contract.md` to say so explicitly, so it doesn't get missed the
  same way for a future action of this shape.
- **Test assertion comparing a `UUID` to a `str`.**
  `test_setting_is_primary_unsets_the_previous_primary_atomically` read
  `id` back from `database_rows` (psycopg returns a `UUID` object) and
  compared it directly to `second.json()["id"]` (a JSON string). Correct
  behavior, wrong assertion. Fixed by wrapping the DB value in `str(...)`.

## Design decisions made during implementation

- **PATCH authorization order differs from `contacts.py`'s.** `contacts.py`
  checks `contact:update` *before* looking up the row, using the
  path-supplied `contact_id` directly, so an unauthorized caller always
  gets `403` regardless of whether the contact exists. Here, the owning
  `contact_id` isn't known until the phone-number/address row itself is
  looked up (the id in the path is the phone-number/address id, not the
  contact id), so the lookup necessarily happens first: a nonexistent
  `phone_number_id`/`address_id` yields `404` (matching detail-`GET`
  concealment), while an existing-but-out-of-scope row yields `403`
  (revealing that *something* exists there, but not what). No test in
  this contract currently exercises that boundary distinction; it's
  documented here as a deliberate, reasoned choice rather than an
  oversight, should it come up in a future review.
- **`is_primary`'s atomic swap is implemented on both `POST` and `PATCH`.**
  The contract's `POST` section describes the atomic unset explicitly; the
  `PATCH` section doesn't restate it, but the invariant (`at most one
  current primary`) is enforced by the partial unique index regardless of
  which endpoint changes it, so `PATCH …{"is_primary": true}` unsets any
  other current primary for the same contact in the same transaction, for
  consistency and to avoid a preventable `UniqueViolation`. Only the
  `POST` case has a dedicated test; the `PATCH` case is covered implicitly
  by the same index that would otherwise error.
- **Addresses have no dedicated Main-Contact/Group-Leader write test.**
  `test_contact_details_endpoints.py`'s docstring states the intent
  explicitly: the self/Main-Contact/Group-Leader write-access model is
  exercised exhaustively once, against phone numbers, and addresses only
  spot-check what's new to that resource (default `address_type`, `self`
  create, outsider denial, end-dating) since both actions share the exact
  same policy shape end to end.

## Deployment notes

No infrastructure changes — no new mounts, no new environment variables.
`schema.sql` gained two `CREATE TYPE` enums and two tables plus their
indexes; applied automatically to a fresh database via the existing
`docker-entrypoint-initdb.d` mechanism. No migration path exists yet for
already-running databases (matches the project's current state — no
migration tooling has been introduced for any prior increment either).

## Not in this increment

Carried over unchanged from `contact-data-expansion-design.md`: bulk
import, any "primary address" concept, and phone/postal format
validation.

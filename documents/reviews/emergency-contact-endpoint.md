# Emergency contact review

## Delivered scope

The third data category from `contact-data-expansion-design.md`. One new
table, `contact_emergency_contacts` — an ordered, per-contact list of who
to contact in an emergency, each entry a foreign key to another CRM
contact (never free text). Full CRUD at
`/api/v1/contact-emergency-contacts` (`GET` list, `GET` detail, `POST`,
`PATCH`, and — the one exception in this system — a genuine `DELETE`,
since this table deliberately carries no `start_date`/`end_date` and this
session never asked for a queryable history of past emergency contacts.

Two access-control decisions, both confirmed with the user before
implementation since the design doc's own wording was ambiguous or
under-specified on them:

- **Reading requires a new `contact:view-sensitive` action, not
  `contact:view`.** Per this session's decision, its rule set mirrors
  `contact:view`'s *entire* current rule set exactly (admin, Area Manager,
  Group Leader `group_descendants` and `group_and_family`, family
  `Parent`, `self`) rather than the role-only subset the design doc's
  prose literally listed — so a contact can see their own emergency
  contacts and a parent can see their child's, not just organisational
  roles. Kept as its own action (not a new rule on `contact:view`) so it
  can be tightened independently later — e.g. requiring a
  safeguarding-training flag — without touching ordinary contact
  visibility.
- **Writing uses a new `contact-emergency-contact:update` action**, the
  same shape as `contact-phone:update`/`contact-address:update`/
  `contact-personal:update`: admin, self, the family's current Main
  Contact, a Group Leader over their exact group and its members'
  families.

Contract: `documents/api-contract.md` "Emergency contact". Schema:
`documents/database/db.dbml`, `database/schema.sql`. Executable coverage:
`tests/api/test_contact_emergency_contacts.py` (21 cases).

## TDD evidence

- All 21 cases confirmed red before implementation (404s from missing
  routes).
- First implementation pass (schema, `contact:view-sensitive` and
  `contact-emergency-contact:update` policy actions, models, router,
  `main.py` registration, CORS `allow_methods` gaining `DELETE`) landed
  all 21 green immediately — no red-to-green bug found in this router
  itself.
- Full suite: 300 collected, 243 contract-marked passing (up from 222),
  54 regression passing — both on a fresh database and repeated without a
  reset.

## Issues found and fixed

- **`require_json_write` unconditionally required
  `Content-Type: application/json`, which a bodyless `DELETE` never
  sends.** Caught before running any test, while implementing the
  `DELETE` endpoint and re-reading the contract's own "not required for
  `DELETE`, which has no body" line — using `require_json_write` as-is
  would have made every legitimate `DELETE` fail with `415`. Fixed by
  splitting `write_security.py`: `require_write` now does the shared
  Origin/CSRF check alone, and `require_json_write` calls it and adds the
  `Content-Type` check on top. `DELETE /contact-emergency-contacts/{id}`
  depends on `require_write`; every other write endpoint in the system is
  unaffected (`require_json_write`'s signature and behavior are
  unchanged, confirmed by the full suite staying green). `main.py`'s CORS
  `allow_methods` also gained `DELETE`, needed for the same reason `PATCH`
  is already listed there.

## Design decisions made during implementation

- **Priority conflicts return `409`, not an atomic reshuffle.** Unlike
  phone numbers' `is_primary` (a single boolean flag the system already
  owns the invariant for), `priority` is an explicit ordinal the client
  fully controls; auto-renumbering other rows on a conflicting `POST`/
  `PATCH` could silently change data the caller didn't ask to change. The
  caller reorders explicitly by patching the conflicting row first.
- **`emergency_contact_id` referencing a nonexistent contact is `422`, not
  `404` or `409`.** Treated as a payload validation failure (the
  referenced ID doesn't name a valid contact) rather than a not-found or
  conflict, caught via `ForeignKeyViolation` at the database.
- **`DELETE` still requires `If-Match`.** Not stated explicitly in the
  design session, but decided during contract-writing for consistency:
  every other mutation in this system is protected against acting on a
  stale view of a resource, and deletion is the one mutation where acting
  on stale data is least recoverable (no undo). `428`/`422`/`412` follow
  exactly the same rules as `PATCH`.

## Deployment notes

No infrastructure changes. `schema.sql` gained one new table (`contact_id
<> emergency_contact_id` check constraint, two unique constraints, two
`ON DELETE RESTRICT` foreign keys); applied automatically to a fresh
database. `main.py`'s CORS configuration now allows `DELETE`. No
migration path exists yet for already-running databases (unchanged
project-wide state).

## Not in this increment

- Any notification or reminder tied to emergency contacts.
- Restoring a deleted emergency contact — there is no undo; re-`POST` it.

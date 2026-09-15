# Organisation-wide address book review

## Delivered scope

The second four-phase cycle covers the organisation-wide address book: `GET
/api/v1/address-book`, `GET /api/v1/address-book/{contact_id}`, and
`GET`/`PATCH /api/v1/address-book/visibility`. Contract:
`documents/api-contract.md` "Organisation-wide address book". Executable
coverage: `tests/api/test_address_book_endpoints.py` (contract) and
`tests/api/test_address_book_scope.py` (regression). Design rationale:
`documents/family-and-directory-design.md`. Database: three
`hidden_from_directory` columns on `contacts`, `contact_roles_groups`, and
`user_access_role_assignments`, added directly to `schema.sql` and
`documents/database/db.dbml` per the "no live database yet" rule in
`way-of-working.md`.

## TDD evidence

- The stale `crm-pytest` database volume initially made every address-book
  test fail with 404 or `UndefinedColumn`, because the volume predated this
  increment's schema change — Postgres only reapplies `schema.sql` on a fresh
  volume. This was an environment artifact, not implementation red; the
  volume was reset (`down -v`) before evidence was collected.
- Against a fresh volume, the existing implementation already passed all
  208 tests (2 smoke, 155 contract, 51 regression) both on first run and on a
  repeat without a database reset.
- Review reproduced one real gap (below), added two regression cases to pin
  it down, confirmed both failed for the intended reason (200 instead of
  422), fixed the implementation, and reran: 210 tests pass, both fresh and
  on a repeat without a database reset.

## Issues found and fixed

1. **PATCH `/address-book/visibility` accepted role ids beyond "current
   eligible assignments".** The contract states: "An `id` that is not one of
   the caller's own current eligible assignments returns 422." The
   implementation validated only *ownership* (`contact_id` / `user_account_id`
   match), not role type or active-date window — the same filters `GET`
   already applies in `_load_visibility`. A caller could hide/unhide a role
   assignment id they own but that is expired, not yet eligible, or of a
   non-eligible role type (e.g. a future Committee Member row), receiving 200
   instead of the documented 422. Not a privilege escalation — a contact can
   only ever touch its own rows, and the flag is inert on any row the
   directory query doesn't already filter for — but a real contract/
   implementation drift with no regression coverage.
   - Added `test_directory_visibility_patch_rejects_an_ended_own_role_id` and
     `test_directory_visibility_patch_rejects_an_ineligible_own_role_type_id`
     to `test_address_book_endpoints.py`; both failed red (200) before the
     fix.
   - Fixed by adding the same eligibility filters (`role_types.name = ANY(...)`
     / `access_roles.is_global`, plus the active-date window) to the
     ownership queries in `update_directory_visibility`
     (`app/routers/address_book.py`), so PATCH now accepts exactly the set of
     ids GET already returns.

## Prioritized follow-up improvements

1. **Duplicated eligibility role list.** `ELIGIBLE_GROUP_ROLE_TYPES` in
   `app/routers/address_book.py` and the `directory:view` rules in
   `app/policies/authorization.toml` independently encode "Group Leader,
   Group Helper, Area Manager". They agree today, but nothing enforces that:
   editing one without the other would silently desync "who can browse the
   directory" from "who is listed in it" — the opposite of
   `authorization-architecture.md`'s own rule that shared authorization logic
   belongs in `AuthorizationService`, not routers. Worth consolidating (for
   example, having the router derive its role-type list from the loaded
   `directory:view` policy rules) the next time this code is touched.
2. **No audit-failure rollback test for this endpoint.** `contact-writes`
   added an explicit test injecting an audit-insert failure and asserting the
   resource change rolled back with it. The address-book PATCH relies on the
   same connection-per-request transaction semantics (verified by inspection:
   the `with psycopg.connect(...)` context manager in `database.py` rolls
   back on any exception propagated from the route, including the mid-patch
   422 for an unknown role id), but that guarantee isn't independently
   exercised for this endpoint the way it was for contact writes.
3. **Collection scalability** (carried over from `reviews/contact-writes.md`):
   `directory:view`'s "holds this role somewhere" check reuses
   `AuthorizationService.groups_by_role`, which materializes the full
   recursive descendant set even though only non-emptiness is needed here.
   Not a correctness issue at current data sizes; revisit alongside the
   existing scalability follow-up.

## Deployment and operational limits

No migration is required — this task applied the new columns only to a
disposable test project via a fresh `schema.sql`-initialized volume. All
three `hidden_from_directory` columns default to `false`, so no backfill
decision is needed. Any directory-eligible adult (current Group Leader,
Group Helper, Area Manager in any group, or any `is_global` access role) can
browse the whole directory and manage their own visibility; nothing else
changed about existing hierarchy-scoped endpoints. No frontend directory UI
is included in this cycle.

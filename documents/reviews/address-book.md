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

## Addendum: `group_id` filter (2026-09-15)

Small follow-on increment, run through the same Phase 1 cycle
([`way-of-working.md`](../way-of-working.md)), adding org-structure
filtering to `GET /api/v1/address-book` ahead of the frontend work that
needs it — the contract deliberately excluded any filtering when the
endpoint first shipped.

- **Contract**: `documents/api-contract.md` "Directory access" now documents
  an optional `group_id` query parameter, descendant-inclusive, malformed
  UUID → 422, no-match or empty-branch → `200` with an empty page (not
  404 — this is a collection filter, not a detail lookup).
- **TDD evidence**: six new cases across
  `tests/api/test_address_book_endpoints.py` (malformed UUID, unknown
  group) and `tests/api/test_address_book_scope.py` (named group plus a
  control contact outside it, descendant groups plus a sibling-branch
  control, an unrelated branch excluded). All six confirmed red — the
  parameter was accepted but silently ignored — before implementation.
  The first two scope cases initially asserted inclusion only, which
  passed against the unfiltered endpoint without proving anything; they
  were strengthened to also assert a control contact's exclusion before
  being trusted as a red baseline.
- **Implementation**: `app/routers/address_book.py`'s `DIRECTORY_CANDIDATES_CTE`
  gained a `group_id_filter` / `descendant_groups` pair (the same
  recursive-descendant shape as `AuthorizationService.groups_by_role` in
  `app/authorization.py`, walking down from one supplied group instead of a
  user's own assignments) and now only contributes `directory_group_roles`
  candidates within that set when a filter is active. An `is_global` access
  role assignment has no group of its own, so it never matches an active
  `group_id` filter — documented explicitly in the contract rather than left
  as an implicit consequence. `get_address_book_entry` passes a constant
  `NULL` filter so its behavior is unchanged.
- **Result**: 215 tests pass (up from 210), both on a fresh database and on
  a repeat without a reset. No schema change, no new authorization action —
  `directory:view`'s eligibility gate is unchanged; the filter only narrows
  what an already-eligible viewer sees, consistent with the address book
  being intentionally org-wide rather than branch-scoped.
- **Follow-up carried forward, not new**: the recursive CTE now runs on
  every address-book request, filtered or not (it's a no-op when
  unfiltered, since the seed row's `group_id` is `NULL`). Covered by the
  existing "Collection scalability" follow-up above — revisit at the same
  time.

## Deployment and operational limits

No migration is required — this task applied the new columns only to a
disposable test project via a fresh `schema.sql`-initialized volume. All
three `hidden_from_directory` columns default to `false`, so no backfill
decision is needed. Any directory-eligible adult (current Group Leader,
Group Helper, Area Manager in any group, or any `is_global` access role) can
browse the whole directory and manage their own visibility; nothing else
changed about existing hierarchy-scoped endpoints. No frontend directory UI
is included in this cycle.

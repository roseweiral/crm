# Contact write increment review

## Delivered scope

The first four-phase cycle covers contact POST and PATCH. Contract:
`documents/api-contract.md`. Executable coverage: `tests/api/test_contact_writes.py`.
Other resource writes remain subsequent cycles, as listed in the contract.

## TDD evidence

- Before implementation: all 55 initial contact-write cases failed on absent
  routes, ETags, or write behavior. The previous 104 tests passed independently.
- After implementation: all 55 cases passed.
- Review reproduced three additional failures: NUL in names reached PostgreSQL,
  embedded newline names were accepted, and simultaneous self-archive requests
  returned a deadlock-driven 500. All three now have passing regression tests.
- Added OpenAPI, mandatory security-header, database-constraint, and migration
  repeatability/collision checks. The full suite contains 167 tests.
- Final validation: 2 smoke, 124 contract, and 41 regression tests passed twice,
  including a repeat without database reset. One upstream Starlette/AnyIO
  deprecation warning remains; no test failures or teardown errors occurred.

## Improvements applied

- Separate input models whitelist editable fields and preserve omitted/null PATCH
  semantics. Shared constraints normalize input before SQL execution.
- A shared origin/custom-header dependency protects new resource writes. CORS
  exposes concurrency and location headers to the configured frontend.
- Database uniqueness handles normalized email collisions atomically; the migration
  fails safely on existing duplicates and has a documented upgrade path.
- A contact row lock and strong ETag comparison prevent stale and concurrent writes.
- Resource writes, session revocations, and success audit records share a transaction.
  Tests inject audit failure and verify complete rollback.
- Authentication activity updates use a short independent transaction. This releases
  session locks before resource handlers lock contacts, eliminating the reproduced
  concurrent self-archive deadlock. Revoked sessions are rechecked by the activity
  update and cannot be refreshed back into validity.
- Audit records contain actor IDs, target IDs, and field names rather than profile
  values or secrets. Fixtures remove endpoint-created records after failures.

## Prioritized follow-up improvements

1. **Security consistency:** migrate invitation and sign-out clients to the shared
   write protection before enforcing it on those existing endpoints. The contact
   change deliberately avoids silently breaking their current clients.
2. **Permission identifiers:** remove policy dependence on mutable role names before
   adding reference-data renaming. Define relationship-management permissions before
   family and role assignment writes.
3. **Database connections:** introduce a bounded connection pool and measure request
   latency under load. Session activity now uses a second short connection; pooling
   should preserve its independent transaction and the deadlock regression test.
4. **Collection scalability:** authorization currently materializes permitted IDs in
   memory. Measure realistic data sizes and consider SQL-scoped joins before large
   deployments. Preserve ordering, total counts, and denial semantics.
5. **Shared resource operations:** the read routers repeat pagination and lookup SQL.
   Extract common pieces only when the next write resource establishes a concrete
   repeated pattern; keep resource-specific validation and policy decisions explicit.
6. **Account recovery:** retain the documented Microsoft verified-email and closed
   account recovery limitations until dedicated onboarding/recovery contracts exist.

## Deployment and operational limits

Apply `database/migrations/001_contact_email_uniqueness.sql` to existing databases
before deploying contact writes. This task applies it only to a disposable test
project. Fresh databases contain the index in `schema.sql`.

Only current Global System Administrators can write contacts. Clients must send the
configured Origin and X-CRM-CSRF header; PATCH additionally requires If-Match. No
frontend editing UI, PUT, DELETE, or other resource writes are included in this cycle.

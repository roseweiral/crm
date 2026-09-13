# API contract

This document defines intended behavior. FastAPI models and route descriptions
publish the implemented schemas through `/openapi.json` and `/docs`; pytest tests
in `tests/api/` enforce the behavior below. Change this contract and its tests
before changing externally visible behavior.

## Scope and delivery

The first increment is contact POST and PATCH, plus ETags on contact detail GET.
Existing collection and authentication behavior remains compatible. PUT, DELETE,
and writes to other resources are future increments, not implemented promises.
Each increment follows documentation → failing tests → implementation → review;
see [`way-of-working.md`](way-of-working.md) for the detailed cycle.

## Shared conventions

- Resources use `/api/v1` and UUID identifiers. GET never changes resource data.
- POST creates a resource and returns 201, its detail representation, and a relative
  `Location` header. PATCH returns 200 and the updated detail representation.
- PATCH changes only supplied fields. Explicit null clears nullable fields; it is
  invalid for required fields. Empty patches and unknown fields return 422.
- Future PUT will replace all editable fields of an existing resource; it will not
  create missing resources. Future DELETE semantics must be specified per resource.
- IDs, timestamps, login flags, and account privileges are server managed.
- Errors retain the existing `{"detail": ...}` envelope. Validation errors use
  FastAPI's structured detail list; other errors use a neutral string.
- 401: no valid session. 403: authenticated user lacks write permission, or fails
  CSRF protection. 404: target record absent. 409: duplicate email. 415: unsupported
  request media type. 422: malformed UUID/body/header. 428: missing If-Match.
  412: a valid supplied ETag no longer matches the current representation.
- When several errors apply, do not depend on validation order. Unauthorized writes
  never disclose whether the target exists or whether an email is already used.

## Write authorization and CSRF

Only a current Global System Administrator may create or update contacts in this
increment, via separate `contact:create` and `contact:update` policy actions.
Viewing a contact, being a parent, or holding a group role does not grant editing.
Future scoped writes must check both ends of a relationship and restrict fields
that can grant permissions.

New contact writes require all of:

- A valid `crm_session` cookie.
- `Content-Type: application/json` (an optional charset parameter is accepted).
- An `Origin` exactly matching a configured `CORS_ORIGINS` entry. Missing, `null`,
  wildcard, and untrusted origins are rejected; configure exact scheme/host/port.
- `X-CRM-CSRF: 1`, a required custom header. It is a browser preflight signal,
  not a secret. CLI clients must also send the Origin and custom header.

CORS permits GET, POST, PATCH and OPTIONS and exposes ETag and Location. It never
permits wildcard credentialed origins. The header-plus-origin approach follows
[OWASP's API CSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html#employing-custom-request-headers-for-ajaxapi).
This increment applies these requirements to contact writes; existing invitation
and sign-out clients are not migrated by this change.

## Contact creation

`POST /api/v1/contacts`

| Field | Requirement |
| --- | --- |
| first_name | Required string; trim surrounding whitespace; 1–100 characters; no embedded control characters |
| last_name | Required string; trim surrounding whitespace; 1–100 characters; no embedded control characters |
| email | Optional, defaults to null; valid email syntax, trim and lowercase; empty string invalid |
| status | Optional; active (default), inactive, or archived |

Return the existing ContactDetail shape, plus ETag and Location headers. The server
sets ID, timestamps, and `can_login=false`. Creating a contact never creates a login
account, external identity, invitation, or role assignment. Email uniqueness is
case insensitive and ignores surrounding whitespace, including legacy rows.
Multiple contacts may have null email. Duplicate creation returns 409; retrying POST
is not an idempotent operation.

## Contact editing and concurrency

`PATCH /api/v1/contacts/{contact_id}`

Accept any nonempty subset of first_name, last_name, email, and status, using the
same validation as creation. Only email may be explicitly null. Profile changes do
not modify `user_identities`, verified login email, or account privileges.

Obtain the current strong ETag from GET `/api/v1/contacts/{contact_id}` or a previous
successful write. Send that exact quoted value in `If-Match`. This API accepts one
strong tag only: wildcard, weak tags, and lists return 422. Missing headers return
428. An outdated tag returns 412 without changing the resource or writing a success
audit event. Concurrent updates using one tag allow at most one success. PATCH
never upserts a missing contact. No-op values are accepted and still count as an
update; refetch the returned ETag. ETags are opaque; clients must not construct them.

Changing status to archived revokes all existing sessions for the contact's account
in the same transaction. Reactivating the contact does not restore those sessions.
The account lifecycle and identity linkage otherwise remain unchanged. History and
relationships remain intact; hard deletion is not part of this increment.

## Transactions and audit

Resource changes and `contact.created` / `contact.updated` success audit events
commit together. Audit failure must roll back the resource change, including any
session revocations. Events identify the actor and contact ID; update events list
changed field names. Do not log profile values, email addresses, or session secrets.
Session last-seen activity is recorded in a short, separate transaction so it
does not hold session locks while a resource write acquires contact locks.
Rejected requests never create a success event. Existing authentication rejection
logging remains separate from these resource transactions.

## Database deployment

Fresh databases include a unique index on lower(trim(email)). Existing databases
must apply `database/migrations/001_contact_email_uniqueness.sql` before enabling
writes. The migration is transactional and fails if existing normalized emails
collide; resolve those duplicates explicitly rather than deleting or merging data
automatically. See `database/migrations/README.md` for the check and application steps.

## Following increments (design pending)

1. Family creation and membership add/change/remove; delete only empty families.
2. Role/group assignments, date validation, end dating and correction deletion.
3. Group creation/editing/movement with cycle and dependency checks.
4. Reference data writes after stable policy identifiers replace role-name coupling.
5. Restricted invitation listing and revocation; separate account recovery design.

Their exact schemas, permissions, errors, and deletion semantics must be documented
and tested before implementation. Contact PUT and filtering improvements will be
specified separately when a client needs them.

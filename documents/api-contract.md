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

The second increment, specified below, is the organisation-wide address book and its self-service visibility settings.

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

## Organisation-wide address book

Resolves [open questions](open-questions.md) #3 and #7's cross-branch case; full
background and rationale live in
[`family-and-directory-design.md`](family-and-directory-design.md). This
increment adds a read-only, org-wide directory of adult volunteers, plus
self-service control over your own presence in it. It does not depend on the
still-pending Young Member role type or on any family/Main Contact write —
neither is a prerequisite.

### Eligibility

A contact is a directory entry if all of the following hold:

- `contacts.status = 'active'`.
- `contacts.hidden_from_directory = false`.
- They hold at least one currently active (`start_date <= current_date` and
  `end_date IS NULL or end_date >= current_date`), non-hidden assignment that
  is either a `contact_roles_groups` row whose role type is Group Leader,
  Group Helper, or Area Manager (never Young Member, once that role type
  exists), or a `user_access_role_assignments` row whose access role has
  `is_global = true` (this reads the existing flag rather than naming "Global
  System Administrator" directly, so it keeps working if another global role
  is added later).

A contact who meets this bar shows only the individual role or assignment
rows that are not themselves hidden. Hiding every one of a contact's eligible
roles has the same visible effect as hiding the contact entirely, even though
the two flags are stored and edited separately.

Visibility is uniform regardless of who is asking; there is no
requester-aware override. Nobody needs one, because a Group Leader, Area
Manager, or Global System Administrator with hierarchical scope over a
person already sees that person's full, unfiltered record through the
existing `GET /api/v1/contacts` and `GET /api/v1/contact-role-groups`
endpoints, neither of which has any concept of directory visibility. That
satisfies "cannot hide from your own leadership" structurally: the address
book only ever changes what a peer with no hierarchical scope over you can
see.

### Directory access

`GET /api/v1/address-book`

Paginated the same way as every other collection (`items`, `page`,
`page_size`, `total`; default `page_size=25`, maximum 100; invalid pagination
returns 422). Ordered by `last_name, first_name, id`.

Accepts an optional `group_id` query parameter to filter results by
organisation structure. When present, only directory entries whose
directory-eligible role or assignment (see Eligibility) is attached to that
group, or to any descendant of it, are returned — the same
descendant-inclusive semantics used everywhere else in the hierarchy. A
malformed `group_id` returns 422. A `group_id` that doesn't match any group,
or that matches a real group with no eligible people under it, returns 200
with an empty `items` array and `total: 0` — this is a collection filter, not
a detail lookup, and an empty result is an ordinary outcome, not an error.
Omitting `group_id` returns the whole directory, unchanged from before.
Pagination applies to the filtered set; changing the filter is expected to
reset the caller to page 1, which is a client concern, not an API one.

Requires the caller to hold at least one currently active role or assignment
of the kinds listed under Eligibility — the address book is a directory *for*
volunteers, not a listing every signed-in contact can browse. An
authenticated contact with none of those (an ordinary parent, a child, or
once it exists, a Young Member) receives 403. An unauthenticated request
receives 401.

Each item:

| Field | Description |
| --- | --- |
| contact_id | The contact's ID |
| first_name, last_name | As stored on the contact |
| email | The contact's email, or null |
| roles | Array of this contact's visible eligible roles (see below) |

Each entry in `roles` is one of:

```json
{"kind": "group_role", "role_type_name": "Group Leader", "group_id": "...", "group_name": "Croydon Group 1", "group_path": [{"id": "...", "name": "HQ"}, "..."]}
```

```json
{"kind": "access_role", "access_role_name": "Global System Administrator"}
```

`group_path` lists ancestors from the hierarchy root down to the assigned
group inclusive, so a client can render the org structure without a second
request.

`GET /api/v1/address-book/{contact_id}` returns one entry in the same shape.
A contact who is not currently a directory entry — not eligible, fully
hidden, or nonexistent — returns 404 with
`{"detail": "Address book entry not found"}`, the same privacy-preserving
pattern used elsewhere for out-of-scope records. A malformed UUID returns
422.

Unlike family units, an address book listing shows full entries rather than
bare IDs with detail deferred to a second request, because browsing the
directory is the point of the list endpoint.

### Self-service visibility settings

`GET /api/v1/address-book/visibility` and `PATCH /api/v1/address-book/visibility`

A contact's own visibility preferences, always scoped to the caller — there
is no `{contact_id}` path parameter, the same pattern `GET /api/v1/me`
already uses. Any authenticated contact may read and write their own
settings, whether or not they currently hold an eligible role; the
preference is harmless to store ahead of time and takes effect only once, or
if, they do.

GET returns:

```json
{
  "hidden_from_directory": false,
  "roles": [
    {"id": "...", "kind": "group_role", "role_type_name": "Group Leader", "group_name": "Croydon Group 1", "hidden_from_directory": false},
    {"id": "...", "kind": "access_role", "access_role_name": "Global System Administrator", "hidden_from_directory": false}
  ]
}
```

`roles` lists only the caller's currently active eligible assignments (ended
assignments are omitted) and — unlike the public directory view — always
includes ones the caller has already hidden, since they need to see a role
to un-hide it.

PATCH accepts any nonempty subset of `hidden_from_directory` (the
whole-profile flag) and `roles` (a list of
`{"id": "...", "hidden_from_directory": true}` patches to specific
assignments). An `id` that is not one of the caller's own current eligible
assignments returns 422. An empty patch returns 422, matching the general
PATCH rule in Shared conventions.

Concurrency and write protection mirror the contact-writes contract exactly:
obtain the strong ETag from the GET, send it in `If-Match` (428 missing, 412
stale, 422 for anything other than one strong tag), and send the configured
`Origin` and `X-CRM-CSRF: 1` header (403 otherwise) — the same shared
dependency contact writes already use, not a new one. A successful PATCH
commits with a `directory_visibility.updated` audit event identifying the
actor and which fields or role IDs changed, following the transaction and
audit rules already agreed for contact writes.

### Database changes

Three new columns, added directly to `database/schema.sql`:

- `contacts.hidden_from_directory boolean NOT NULL DEFAULT false`
- `contact_roles_groups.hidden_from_directory boolean NOT NULL DEFAULT false`
- `user_access_role_assignments.hidden_from_directory boolean NOT NULL DEFAULT false`

All default to visible, so existing rows need no backfill decision.
[`documents/database/db.dbml`](database/db.dbml) is the source of truth and
already reflects these three columns; `schema.sql` is written to match it, not
the other way around. There is no live database yet, so this increment
declares the columns directly in `schema.sql` rather than writing a migration
under `database/migrations/` — every environment is still built fresh from
`schema.sql` plus demo/seed data, per [`way-of-working.md`](way-of-working.md).
A migration becomes necessary only once a real database exists that this
change must be applied to without a reset. This increment starts here, at the
database layer, before any route or test — consistent with the note in
`family-and-directory-design.md`.

### Authorization policy

Two new actions in `app/policies/authorization.toml`:

- `directory:view` (resource: directory entry) — granted with `scope = "all"`
  to anyone currently holding Group Leader, Group Helper, or Area Manager (in
  any group), or an `is_global` access role. This is a new combination for
  the policy engine: `source = "group_role"` paired with `scope = "all"`
  rather than `scope = "group_descendants"`, because eligibility here means
  "holds this kind of role somewhere," not "holds it over a specific
  branch." `AuthorizationService` needs to support that combination before
  this ships.
- `directory-visibility:manage-own` (resource: directory entry) —
  `source = "self"`, `scope = "self"`, granted to every authenticated
  contact regardless of current role, matching the existing self rule
  already used for `contact:view`.

### Not in this increment

- Skills and photo fields (explicit future vision — see
  `family-and-directory-design.md`).
- Free-text or name search, and any filter beyond `group_id` and plain
  pagination.
- An administrator managing another contact's visibility settings on their
  behalf; only self-service is built now.
- The Young Member role type and any role or group write increment —
  unrelated and not a dependency.

## Documentation browser

Read-only access to the project's own markdown documentation from inside
the signed-in application, so it doesn't only exist as files in the repo.
Available to any authenticated contact — this is process/architecture
documentation, not CRM data, so it carries no further authorization scope
beyond having a valid session (the same "just needs to be signed in" shape
`GET /api/v1/me` already uses).

The servable set is a fixed, hardcoded manifest — id, repo-relative path,
title, category — not a directory scan. A request for an `id` outside that
manifest is a 404; the value is never used to build a filesystem path. This
is a deliberate security property, not an incidental implementation detail:
it removes path traversal as a possible bug class for this feature rather
than needing to be defended against per request.

### Listing

`GET /api/v1/documents`

Returns every manifest entry, ordered by category then title:

```json
{
  "items": [
    {"id": "way-of-working", "title": "Way of working", "category": "Architecture and process", "path": "documents/way-of-working.md"},
    "..."
  ]
}
```

No pagination — the manifest is small and fixed. 401 for no session.
`path` is included on every item, not only on the detail response: the
frontend needs every document's path up front (not just the currently open
one) to resolve a markdown link found in one document's content into
another manifest entry — see the "Detail" section's note on `path` below.

Categories mirror this repository's own [documentation
index](../README.md#documentation-index): `Overview`, `Architecture and
process`, `Authentication and authorization`, `API and testing`, `Data`,
`Deployment`.

### Detail

`GET /api/v1/documents/{id}`

```json
{
  "id": "way-of-working",
  "title": "Way of working",
  "category": "Architecture and process",
  "path": "documents/way-of-working.md",
  "content": "# Way of working: feature increments\n\n..."
}
```

`content` is the raw markdown text, unrendered — rendering happens in the
frontend. `path` is this document's own repo-relative path: resolving a
relative markdown link inside `content` (for example `way-of-working.md`
linking to `open-questions.md`) starts from *this* path, and is checked
against every other document's `path` from the list response to decide
whether it becomes an in-app link.

A malformed or unknown `id` returns 404 with `{"detail": "Document not
found"}`. 401 for no session.

### Not in this increment

- Search across document content.
- Any document outside the fixed manifest (in particular
  `documents/database/db.dbml`, which isn't markdown prose).
- Editing documentation from the app — this is a read-only mirror of what's
  already in the repo.

## Following increments (design pending)

1. Family creation and membership add/change/remove; delete only empty families.
2. Role/group assignments, date validation, end dating and correction deletion.
3. Group creation/editing/movement with cycle and dependency checks.
4. Reference data writes after stable policy identifiers replace role-name coupling.
5. Restricted invitation listing and revocation; separate account recovery design.

Their exact schemas, permissions, errors, and deletion semantics must be documented
and tested before implementation. Contact PUT and filtering improvements will be
specified separately when a client needs them.

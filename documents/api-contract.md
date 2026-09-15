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

The second increment, specified below, is the organisation-wide address book and its self-service visibility settings. The third is the read-only documentation browser. The fourth, fifth, and sixth are the three contact-data-expansion prerequisites (Main Contact tracking, the Group-Leader-exact-group write scope, and its family extension). The seventh is contact details (phone numbers and addresses). The eighth
is personal details (date of birth, preferred name, phonetic name,
pronouns, gender). The ninth is emergency contact — see
[`contact-data-expansion-design.md`](contact-data-expansion-design.md).
It also introduces `contact:view-sensitive`, a new read permission
separate from ordinary `contact:view`. The tenth, specified below, is a
read-only contact profile aggregate for the frontend's contact details
page.

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

A current Global System Administrator may create or update any contact, via
separate `contact:create` and `contact:update` policy actions. Resolving
[open questions](open-questions.md) #4: a current Group Leader may also
update — full field access, including archiving, no restricted subset —
any contact holding an active role in their *exact* assigned group, not
descendant groups, **and every contact sharing a family unit with one of
those group members** (any `contact_family_units` relationship, not only
`parent` — a sibling or guardian in the same family unit is included the
same way). This second part is broader than open question #4 itself asked
for; it's the write-access model agreed in
`contact-data-expansion-design.md` for the contact-data-expansion
categories, applied here to the existing basic fields too so it has a real,
testable consumer rather than sitting unused in the policy engine until
the first new-field category ships. `contact:create` is unaffected:
creating a contact has no group to scope against yet, and combining
contact creation with a group role assignment in one request is not
designed. Viewing a contact, being a parent, or holding any other group
role (Group Helper, Area Manager) does not grant editing. Future scoped
writes must check both ends of a relationship and restrict fields that can
grant permissions.

Two new combinations for the policy engine, both `source = "group_role"`:
`scope = "group"` (the caller's own assigned group only, computed without
the descendant-walking recursion `group_descendants` already uses — see
[`groups_by_role` docs](authorization-architecture.md)), and
`scope = "group_and_family"` (that same exact-group set, extended through
`contact_family_units` to every other member of each group member's family
unit). `contact:update`'s Group Leader rule uses `group_and_family`; `group`
alone remains available for any future action that wants the exact-group
restriction without the family extension.

`contact:view` gains the same `group_and_family` rule for Group Leader too,
additive to its existing `group_descendants` rule (which is unchanged, and
keeps covering the full hierarchy for reads exactly as before). Not an
independent scope decision: the PATCH concurrency pattern requires a prior
GET to obtain the current ETag, so a write-only extension with no matching
read access would be unusable in practice — the same relationship already
implicit everywhere else `contact:update` and `contact:view` overlap.

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

## Main Contact tracking

Resolves the first prerequisite from
[`contact-data-expansion-design.md`](contact-data-expansion-design.md):
who currently holds Main Contact status for a family unit, and an
administrative way to change it. This is deliberately narrower than full
family-membership writes (item 1 under "Following increments" below) —
it does not add, remove, or edit family members or relationships, only
tracks and changes who among the *existing* members is the Main Contact.

### Reading Main Contact status

`GET /api/v1/family-units/{family_unit_id}` gains `is_main_contact` on
each entry in `members`, `true` for at most one member (the one with a
current — `end_date IS NULL` — row in the new
`contact_family_main_contacts` table), `false` for every other member,
including one with no eligible relationship type at all. No change to who
can call this endpoint or to the collection endpoint's shape; `family:view`
already gates this data, and Main Contact status is no more sensitive than
the relationships already returned.

### Changing Main Contact

`POST /api/v1/family-units/{family_unit_id}/main-contact`

```json
{"contact_id": "..."}
```

Sets `contact_id` as the family unit's current Main Contact, ending the
previous holder's tenure (`end_date = today`) in the same transaction a
new row starts (`start_date = today`). Returns 200 with the updated
`FamilyUnitDetail` (the same shape `GET` returns).

- Requires a valid `crm_session`, plus the standard write headers
  (`X-CRM-CSRF: 1`, matching `Origin`, `Content-Type: application/json`) —
  the same `require_json_write` dependency every other write uses. No
  `If-Match`/ETag: this is a single-field state change with a natural
  idempotency key (the target `contact_id`), not a multi-field resource
  edit, so the existing contact-writes concurrency pattern doesn't apply;
  the family unit row is locked `FOR UPDATE` for the duration of the
  check-then-write to serialize concurrent attempts instead.
- Authorization: `family:manage-main-contact`, granted to Global System
  Administrator only for now — matching how contact writes themselves
  started. A safeguarding-driven handover (the motivating example in
  `family-and-directory-design.md`) is exactly the kind of action that
  should stay admin-only until there's a specific reason to widen it, not
  the kind to default open.
- `contact_id` must reference a *current* member of this family unit
  (a row in `contact_family_units` for this `family_unit_id`) whose
  `relationship` is not `child` — matching "any adult relationship type is
  eligible to become Main Contact" from `family-and-directory-design.md`.
  A `contact_id` that isn't a member at all, or is a `child` member, returns
  422 — the same "referenced id must be one of your own/eligible rows"
  pattern already used for `directory-visibility:manage-own`'s role patches,
  not 404, since the family unit itself does exist.
- Setting `contact_id` to whoever is *already* the current Main Contact is
  a no-op: 200, unchanged state, no new history row, no audit event, no
  session revocation. Nothing changed.
- On an actual change: the outgoing Main Contact's active sessions are
  revoked in the same transaction as the handover — the same "archiving a
  contact revokes its sessions immediately" pattern from contact writes,
  applied here per `family-and-directory-design.md`'s explicit note that a
  Main Contact change "should likely revoke the outgoing Main Contact's
  sessions the same way." The incoming Main Contact's account and sessions
  are untouched by this endpoint; whether they can already sign in is a
  separate, existing concern (account status, invitations), not created or
  modified here.
- Commits a `family.main_contact_changed` audit event alongside the
  resource change (same transaction, same rollback-together rule as every
  other write): actor, `family_unit_id`, outgoing and incoming
  `contact_id` — record IDs, not profile values, matching the existing
  audit convention.

### Database changes

New table, added directly to `schema.sql` (no live database yet, per
`way-of-working.md`) and already reflected in `db.dbml`, the source of
truth: **`contact_family_main_contacts`** — `family_unit_id`, `contact_id`,
`start_date`, `end_date` (nullable), timestamps. A partial unique index on
`family_unit_id` where `end_date IS NULL` enforces at most one current Main
Contact per family, mirroring the existing "exactly one active Group
Leader per group" constraint.

### Not in this increment

- Family creation and membership writes (adding/removing members, new
  family units) — item 1 under "Following increments" below.
- The Group-Leader-exact-group write scope and its family extension —
  `contact-data-expansion-design.md`'s Prerequisites 2 and 3, separate
  increments.
- Any change to who can *read* family data — `family:view`'s existing
  scope is unchanged.

## Contact details: phone numbers and addresses

`contact-data-expansion-design.md`'s first actual data category, on top of
its three now-delivered prerequisites. Two new, independent resources —
phone numbers and addresses — sharing the same dated-history shape
(`start_date`/`end_date`, the `contact_roles_groups` pattern) and the same
write-access model, agreed in that design session.

### Write-access model

New actions, `contact-phone:update` and `contact-address:update` — deliberately
distinct from `contact:update`, which keeps its own narrower rules (Global
System Administrator plus Group-Leader-exact-group, per
[open questions](open-questions.md) #4, with no self or Main-Contact rule).
Both new actions grant write access to:

- Global System Administrator (`all`), matching every other write action in
  this system.
- The contact themselves (`self`).
- The current Main Contact of the contact's family unit — a new policy
  source, `main_contact_family`, reading `contact_family_main_contacts`
  (Prerequisite 1's table) and reusing the existing family-resource
  resolution unchanged.
- A Group Leader, for contacts holding an active role in their exact group
  and those contacts' family members (`group_and_family`, reused unchanged
  from Prerequisite 3).

Area Manager and Group Helper get no write rule. Reading either resource
reuses the existing `contact:view` scope directly, unmodified: it's already
a superset of what these write rules grant (for example, it also lets any
parent — not only the Main Contact — view their whole family), so no new
read permission is needed.

### Phone numbers

`GET /api/v1/contact-phone-numbers`

Optional `contact_id` filter; without it, returns every phone number row
the caller's `contact:view` scope covers. Paginated like every other
collection. Includes historical (end-dated) rows as well as current ones —
`end_date IS NULL` is how a client identifies the current set.

| Field | Description |
| --- | --- |
| id | Server-assigned |
| contact_id | Owning contact |
| phone_type | `mobile`, `home`, `work`, or `other` |
| number | Free text — no format validation this increment |
| is_primary | At most one `true` among a contact's *current* numbers |
| start_date, end_date | `end_date` null while current |

`GET /api/v1/contact-phone-numbers/{id}` returns one row plus a strong
ETag, same pattern as contact detail GET. 404 for a phone number outside
the caller's `contact:view` scope, concealing existence like every other
detail endpoint.

`POST /api/v1/contact-phone-numbers`

```json
{"contact_id": "...", "phone_type": "mobile", "number": "...", "is_primary": false}
```

Creates a new, current row (`start_date` defaults to today, `end_date`
null). `is_primary` defaults to `false`. Setting `is_primary: true`
atomically un-sets it on any other current phone number for the same
contact, in the same transaction — the "one current holder, handled
atomically" pattern `contact_family_main_contacts` established, applied
here so a client never needs two round-trips to change which number is
primary. Requires `contact-phone:update` on `contact_id`. 201, `Location`,
ETag.

`PATCH /api/v1/contact-phone-numbers/{id}`

Any nonempty subset of `phone_type`, `number`, `is_primary`, `end_date`.
Setting `end_date` is how a number is retired — no hard deletion, matching
every other resource in this system. `If-Match` required, same strong-tag
rules as contact PATCH (428 missing, 422 malformed, 412 stale). Requires
`contact-phone:update` on the row's `contact_id`.

### Addresses

`GET /api/v1/contact-addresses`, `GET /api/v1/contact-addresses/{id}`,
`POST /api/v1/contact-addresses`, `PATCH /api/v1/contact-addresses/{id}` —
identical shape to phone numbers above (same pagination, `contact_id`
filter, ETag/If-Match concurrency, `contact-address:update` authorization),
with these differences:

| Field | Description |
| --- | --- |
| address_type | `home` (default), `work`, or `other` |
| line1 | Required |
| line2, city, region, postcode, country | All optional |

No `is_primary` — `address_type` already disambiguates concurrent
addresses, and this session's design didn't ask for a separate "preferred"
flag the way phone numbers have one.

### Shared conventions

- Same write-header requirements as every other write: `X-CRM-CSRF: 1`,
  matching `Origin`, `Content-Type: application/json`.
- Resource change and a `contact_phone_number.created`/`.updated` (or
  `contact_address.created`/`.updated`) success audit event commit
  together; audit failure rolls back the resource change, following the
  existing contact-writes transaction rule.
- 401/403/404/415/422/428/412 follow "Shared conventions" above exactly.

### Database changes

Two new tables, added directly to `schema.sql` and already reflected in
`db.dbml`: **`contact_phone_numbers`** (`contact_id`, `phone_type`,
`number`, `is_primary`, `start_date`, `end_date`, timestamps) and
**`contact_addresses`** (`contact_id`, `address_type`, `line1`, `line2`,
`city`, `region`, `postcode`, `country`, `start_date`, `end_date`,
timestamps). A partial unique index on `contact_phone_numbers
(contact_id)` where `is_primary AND end_date IS NULL` enforces at most one
current primary number per contact.

### Not in this increment

- Bulk import or CSV upload of phone numbers or addresses.
- Any "primary address" concept — deliberately not designed this session.
- Validating phone number format or postal address structure beyond the
  required fields above — this increment is data capture, not
  validation or geocoding.

## Personal details

`contact-data-expansion-design.md`'s second data category. Five new,
nullable columns directly on `contacts` (no new table): `date_of_birth`,
`preferred_name`, `phonetic_name`, `pronouns`, `gender`. Surfaced through
the *existing* contact endpoints rather than new ones — `GET
/api/v1/contacts`, `GET /api/v1/contacts/{id}`, and `PATCH
/api/v1/contacts/{id}` — since the data lives on the same row.

| Field | Description |
| --- | --- |
| date_of_birth | Nullable date. Must not be in the future. |
| preferred_name | Nullable free text — the name someone goes by, distinct from `first_name`. |
| phonetic_name | Nullable free text, e.g. `"SHE-von"` for `"Siobhan"` — no controlled vocabulary for pronunciation. |
| pronouns | Nullable free text rather than a fixed list. |
| gender | Nullable free text, same reasoning as pronouns. |

### Reading

Reuses `contact:view` unmodified. The five fields simply appear in
`Contact` (list) and `ContactDetail` (detail) responses alongside the
existing fields — no separate read permission, matching phone numbers and
addresses.

### Writing: one endpoint, two independently-checked authorizations

`contact:update` keeps its existing, narrower rules (Global System
Administrator plus Group-Leader-exact-group only, no self-write —
`open-questions.md` #4) unchanged. A new action, `contact-personal:update`,
grants the full write-access model this design session agreed to
(Global System Administrator; the contact themselves; the family's current
Main Contact; a Group Leader over their exact group and its members'
families) — the same shape as `contact-phone:update` and
`contact-address:update`.

`PATCH /api/v1/contacts/{id}` accepts any nonempty subset of its existing
fields (`first_name`, `last_name`, `email`, `status`) *and* the five new
ones, in one payload, one transaction, one `If-Match`. Which
authorization(s) must pass depends on which fields the payload actually
sets:

- Any of `first_name`/`last_name`/`email`/`status` present → `contact:update`
  must be satisfied for this contact.
- Any of `date_of_birth`/`preferred_name`/`phonetic_name`/`pronouns`/`gender`
  present → `contact-personal:update` must be satisfied for this contact.
- Both groups present in one payload → both checks apply. If either fails,
  the whole request is rejected (403) — no partial writes.

This lets a contact update their own `preferred_name`/`pronouns`/
`date_of_birth` without ever being granted `contact:update` (legal name,
email, and status stay exactly as restricted as before), while an
admin, Main Contact, or Group Leader can change either or both kinds of
field in a single call.

`email` and all five personal-detail fields may be set explicitly to
`null` (clearing a previously-set value); `first_name`, `last_name`, and
`status` may not. Same `If-Match` mechanics as today — the strong ETag
covers the full `ContactDetail` representation, so it changes whenever
any field does, personal or core. The `contact.updated` audit event is
unchanged in shape (`{"contact_id", "fields"}`); `fields` simply may now
include personal-detail field names.

### Not in this increment

- Setting personal-detail fields at contact creation (`POST
  /api/v1/contacts`) — write them via `PATCH` after creation.
- Any format/plausibility validation beyond "`date_of_birth` is not in the
  future" — `preferred_name`/`phonetic_name`/`pronouns`/`gender` are
  unvalidated free text, matching every other free-text field in this
  system.

## Emergency contact

`contact-data-expansion-design.md`'s third data category. One new table,
`contact_emergency_contacts` — an ordered, per-contact list of who to
contact in an emergency, each entry pointing at another CRM contact
(never free text: if the right person isn't a contact yet, they're added
as one, with no login, before being set as an emergency contact).
Deliberately **not** dated/historical, unlike phone numbers and
addresses — this session only asked for the current, ordered list, not a
queryable history of past emergency contacts, so there's no
`start_date`/`end_date` and removal is a genuine `DELETE`, not an
end-dating. (Design doc: "Revisit if that turns out to be wrong.")

| Field | Description |
| --- | --- |
| id | Server-assigned |
| contact_id | Whose emergency contact this is |
| emergency_contact_id | Who to contact — FK to `contacts.id` |
| priority | Integer, `1` = primary, `2` = secondary, etc. |
| relationship | Free text (`"Mother"`, `"Neighbour"`, `"Family friend"`) — not constrained to `family_relationship_type`, since an emergency contact isn't always an existing family relationship |

Constraints: `contact_id <> emergency_contact_id` (422 if equal); unique
`(contact_id, priority)` and unique `(contact_id, emergency_contact_id)`
(409 on either violation — the caller reorders by patching the
conflicting row first, no automatic shifting, unlike phone numbers'
`is_primary` swap: priority is an explicit ordinal the client controls,
and silently renumbering other rows on the caller's behalf could
surprise it).

### Reading: `contact:view-sensitive`, not `contact:view`

Unlike phone numbers, addresses, and personal details, reading emergency
contacts requires a new, separately-grantable action,
`contact:view-sensitive`, rather than riding on ordinary `contact:view` —
so, for example, a Group Helper who can see a child's name and roles
doesn't automatically see who their emergency contact is. Per this
session's decision, `contact:view-sensitive` mirrors `contact:view`'s
*entire* current rule set exactly (Global System Administrator → all;
Area Manager → `group_descendants`; Group Leader → `group_descendants` and
`group_and_family`; family `Parent` → `family`; `self` → `self`) — being a
separate action, rather than a new rule on `contact:view` itself, means it
can be tightened independently later (for example, requiring a
safeguarding-training flag) without touching ordinary contact visibility.

### Writing: `contact-emergency-contact:update`

Same write-access model as `contact-phone:update`/`contact-address:update`:
Global System Administrator; the contact themselves (`self`); the family's
current Main Contact (`main_contact_family`, scope `family`); a Group
Leader over their exact group and its members' families
(`group_and_family`). Area Manager and Group Helper get no write rule.

`GET /api/v1/contact-emergency-contacts` — optional `contact_id` filter;
without it, every row the caller's `contact:view-sensitive` scope covers.
Paginated like every other collection.

`GET /api/v1/contact-emergency-contacts/{id}` — one row plus a strong
ETag. 404 outside the caller's `contact:view-sensitive` scope, concealing
existence like every other detail endpoint.

`POST /api/v1/contact-emergency-contacts` —
```json
{"contact_id": "...", "emergency_contact_id": "...", "priority": 1, "relationship": "Mother"}
```
Requires `contact-emergency-contact:update` on `contact_id`. 422 if
`contact_id == emergency_contact_id` or `emergency_contact_id` doesn't
refer to an existing contact. 409 on a `priority` or
`emergency_contact_id` already used by this `contact_id`. 201, `Location`,
ETag.

`PATCH /api/v1/contact-emergency-contacts/{id}` — any nonempty subset of
`emergency_contact_id`, `priority`, `relationship`. Same `If-Match`,
authorization, and 422/409 rules as `POST`, checked against the row's
existing `contact_id`.

`DELETE /api/v1/contact-emergency-contacts/{id}` — the only hard-delete
endpoint in this system, matching the "not dated/historical" schema
decision above. Requires `contact-emergency-contact:update` on the row's
`contact_id` and the same `If-Match` mechanics as `PATCH` (428 missing,
422 malformed, 412 stale) — deleting a row a client hasn't seen the latest
version of is rejected the same way an out-of-date `PATCH` is. 204 No
Content on success; 404 outside scope.

### Shared conventions

- Same write-header requirements as every other write: `X-CRM-CSRF: 1`,
  matching `Origin`, `Content-Type: application/json` (not required for
  `DELETE`, which has no body).
- Resource change and a `contact_emergency_contact.created`/`.updated`/
  `.deleted` success audit event commit together; audit failure rolls back
  the resource change.
- 401/403/404/415/422/428/412 follow "Shared conventions" above exactly.

### Not in this increment

- Any notification or reminder tied to emergency contacts (e.g. prompting
  a Group Leader to confirm the list is current before an event).
- Restoring a deleted emergency contact — there is no undo; re-`POST` it.

## Contact profile (read-only aggregate)

The frontend's contact details page needs personal details, phone
numbers, addresses, and emergency contacts together, without four
round-trips per page load. Deliberately **not** achieved by embedding
those into `ContactDetail` itself: `ContactDetail`'s ETag drives
`PATCH /api/v1/contacts/{id}`'s optimistic-concurrency check, and folding
in data that changes independently (a phone number edited elsewhere)
would make that ETag go stale for reasons unrelated to what the caller
actually edited. Instead, a separate, read-only, unversioned endpoint:

`GET /api/v1/contacts/{contact_id}/profile`

```json
{
  "contact": { "...": "same shape as GET /api/v1/contacts/{id}" },
  "phone_numbers": [{ "id": "...", "phone_type": "mobile", "number": "...", "is_primary": true }],
  "addresses": [{ "id": "...", "address_type": "home", "line1": "...", "...": "..." }],
  "emergency_contacts": [{
    "id": "...", "emergency_contact_id": "...", "priority": 1, "relationship": "Mother",
    "first_name": "...", "last_name": "...", "email": "...", "phone_number": "..."
  }]
}
```

- `contact`: identical fields to `GET /api/v1/contacts/{id}`, gated by
  `contact:view` exactly as that endpoint is - 404 if the contact doesn't
  exist or is out of the caller's `contact:view` scope, concealing
  existence the same way.
- `phone_numbers`, `addresses`: **current only** (`end_date IS NULL`) -
  this is a "what do I need to know right now" view, not a history
  browser; the existing `GET /api/v1/contact-phone-numbers` and
  `/contact-addresses` collection endpoints remain how historical rows
  are queried. Gated by `contact:view` (unchanged - reused directly, same
  as those endpoints' own read side).
- `emergency_contacts`: gated separately by `contact:view-sensitive`. When
  the caller has `contact:view` but not `contact:view-sensitive` for this
  contact, the key is `null` - meaning "you can't see this" - never `[]`,
  which would misleadingly mean "recorded as having none." Each entry
  embeds the referenced contact's `first_name`, `last_name`, `email`, and
  `phone_number` directly - the whole point of an emergency contact is
  being able to actually reach them, so a page showing this list needs
  that without a second round-trip per entry. `phone_number` is that
  person's current primary number if they have one, else their most
  recently added current number, else `null` if they have none recorded.
  Deliberately **not** gated by a further permission check against the
  referenced person's own record: once the caller is permitted to see
  *whose* emergency contact someone is (`contact:view-sensitive` on the
  contact being viewed), withholding how to reach that person would
  defeat the feature's purpose. `emergency_contact_id` remains present
  too, for a future link to that contact's own profile.
- No `ETag`, no `If-Match` - this endpoint is display-only. Writes still
  go through each resource's own endpoint (`PATCH /api/v1/contacts/{id}`,
  the `contact-phone-numbers`/`contact-addresses`/
  `contact-emergency-contacts` endpoints), each with its own ETag.
- No pagination - a contact has a small, bounded number of current phone
  numbers, addresses, and emergency contacts.
- 401 unauthenticated; no CSRF requirements (a `GET`, like every other
  read endpoint).

### Not in this increment

- Any other resource gaining a `/profile`-shaped aggregate (family units,
  groups) - added only where a real frontend page needs it, per this
  session's decision.
- Including historical (end-dated) phone numbers or addresses in the
  aggregate.
- Medical conditions, once that category ships - this endpoint gains a
  fourth key then, gated by the same `contact:view-sensitive` action
  already used for `emergency_contacts`.

## Following increments (design pending)

1. Family creation and membership add/change/remove; delete only empty families.
   (Main Contact *tracking* — who currently holds it, and changing that —
   is specified above, not deferred; this item is the remaining, larger
   family-membership-write surface: adding/removing members, changing
   relationship types, creating new family units.)
2. Role/group assignments, date validation, end dating and correction deletion.
3. Group creation/editing/movement with cycle and dependency checks.
4. Reference data writes after stable policy identifiers replace role-name coupling.
5. Restricted invitation listing and revocation; separate account recovery design.

Their exact schemas, permissions, errors, and deletion semantics must be documented
and tested before implementation. Contact PUT and filtering improvements will be
specified separately when a client needs them.

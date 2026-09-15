# Contact data expansion

## Status

This records agreed decisions from a design session on expanding what the
CRM stores about a contact, the same way
[`family-and-directory-design.md`](family-and-directory-design.md) preceded
the address book. These are agreed decisions, not yet implemented. Each
category below becomes its own increment through the normal [way of
working](way-of-working.md) — contract update, TDD, implementation, review
— run separately per category rather than as one batch, per
`way-of-working.md`'s existing rule against combining unrelated resources
in one pass.

Today, `contacts` holds only `first_name`, `last_name`, `email`, `status`,
`can_login`, `hidden_from_directory`, and timestamps — see
`documents/database/db.dbml`. Two fields were already on record as intended
future additions before this session: skills (for member search) and a
profile photo, both explicitly deferred out of v1 in
`family-and-directory-design.md`. This session adds to, not replaces, that
backlog.

## Personal details (columns directly on `contacts`) — delivered

See [`reviews/personal-details-endpoint.md`](reviews/personal-details-endpoint.md).

Single-valued, always-belongs-to-exactly-one-contact fields join the
existing bare columns rather than getting their own table:

- `date_of_birth date`, nullable. Revisits open question 8's finding that
  DOB wasn't needed for *automatic family-visibility-by-age* — that
  conclusion stands unchanged; this is a different purpose (general record
  keeping), not a reversal of it.
- `preferred_name varchar`, nullable — the name someone goes by, distinct
  from their legal `first_name`.
- `phonetic_name varchar`, nullable — free text, e.g. "SHE-von" for
  "Siobhan". Has to be free text; there's no controlled vocabulary for
  pronunciation.
- `pronouns varchar`, nullable — free text rather than a fixed list, so it
  never fails to represent how someone actually describes themselves.
- `gender varchar`, nullable — free text, same reasoning as pronouns.

## Contact details: phone numbers and addresses

Both get their own table, both carry history (`start_date`/`end_date`,
the same shape `contact_roles_groups` already uses), per this session's
decision that past addresses *and* past phone numbers should be
queryable, not just current values.

**`contact_phone_numbers`**: `contact_id`, `phone_type` (enum: `mobile`,
`home`, `work`, `other`), `number varchar`, `is_primary boolean default
false`, `start_date`, `end_date`. `is_primary` is orthogonal to the dating —
it picks which of possibly several *concurrent* numbers (mobile and work,
say) is preferred, not which is most recent. A partial unique index keeps
at most one primary, current (`end_date IS NULL`) number per contact.

**`contact_addresses`**: `contact_id`, `address_type` (enum: `home`,
`work`, `other`; defaults to `home`), `line1`, `line2`, `city`,
`region`, `postcode`, `country`, `start_date`, `end_date` — separate
components rather than one free-text block, so a mail-merge or region
filter doesn't have to parse a blob. Addresses stay per-contact rather than
per-family-unit: people in the same family unit can genuinely have
different addresses (separated parents, a young person away from home),
and a "shared family address" can still be read by joining contacts within
a family unit, without a special-cased model for it.

## Emergency contact — delivered

See [`reviews/emergency-contact-endpoint.md`](reviews/emergency-contact-endpoint.md).
Note: the read-scope question this section originally left implicit
(whether `contact:view-sensitive` includes self/family, not just
organisational roles) was resolved during implementation — it does; see
the review and "Sensitive-data read access" below, which now reflects
that decision rather than the narrower role-only wording this section
first proposed.

**`contact_emergency_contacts`**: `contact_id` (whose emergency contact
this is), `emergency_contact_id` (who to contact — a foreign key to
`contacts.id`, never free text, per this session's decision: if the right
person isn't a CRM contact yet, they're added as one, even with no login,
before being set as an emergency contact — one consistent model instead of
two parallel shapes for the same concept), `priority integer` (1 =
primary, 2 = secondary, ...), `relationship varchar` (free text — "Mother",
"Neighbour", "Family friend" — since an emergency contact is not always a
family relationship already captured in `contact_family_units`, and
forcing it into that enum would misrepresent non-family emergency
contacts). Constraints: `contact_id <> emergency_contact_id` (can't be your
own emergency contact), unique `(contact_id, priority)`, unique
`(contact_id, emergency_contact_id)`.

Not dated/historical — unlike addresses and phone numbers, this session
didn't ask for a queryable history of *past* emergency contacts, just the
current, ordered list. Revisit if that turns out to be wrong.

## Medical conditions

Three levels, mirroring the existing `role_types` → `contact_roles_groups`
shape (a curated lookup, then a per-contact link, extended here with a
third level for the ongoing log):

**`medical_condition_types`** (admin-maintained lookup, like `role_types`/
`award_types`): `name` (unique), `description`. Includes an "Other" row so
a condition outside the curated list still has one consistent shape to
attach notes to, rather than a parallel free-text path.

**`contact_medical_conditions`** (which conditions a contact has):
`contact_id`, `medical_condition_type_id`, `start_date` (when recorded/
diagnosed), `end_date` (nullable — when resolved). Unique on `(contact_id,
medical_condition_type_id)`; a resolved-then-recurring condition clears
`end_date` again rather than inserting a duplicate row.

**`contact_medical_condition_notes`** (the "freetext date logging and
notes for each condition" this session asked for): `contact_medical_condition_id`,
`noted_at`, `author_account_id` (who recorded it — the same actor-attribution
already used for audit events, since this is exactly the kind of record
that needs a paper trail), `note text`.

## Communications preferences

Proposed shape, not yet confirmed in detail — this session only confirmed
the category is in scope, not the exact channels or defaults:

**`contact_communication_preferences`** (one row per contact):
`email_opt_in`, `sms_opt_in`, `post_opt_in` (booleans), `preferred_channel`
(enum: `email`, `sms`, `post`, `none`), `consent_recorded_at timestamptz`
(nullable — when consent was last given/changed, likely relevant if this
organisation is UK-GDPR-scoped). Kept as its own table rather than more
columns on `contacts`, since consent tracking is a distinct concern from
identity/contact-method data and is likely to grow its own history
requirements (e.g. a per-channel consent date) sooner than the personal-
details columns above.

## Write-access model

Agreed for every category in this document (phone numbers, addresses,
personal details, emergency contact, medical conditions, communications
preferences) — the same five rules apply uniformly rather than each
category inventing its own:

1. **Self**: a contact may always write their own record's new fields.
2. **Main Contact**: the current Main Contact of a family unit may write
   the record of any contact in that family unit.
3. **Group Leader**: write access to contacts holding an active role in
   their *exact* assigned group — not descendant groups, the same
   restriction already agreed for basic contact writes in
   `open-questions.md` #4 — **plus** those contacts' family members (so a
   Group Leader can update a young member's emergency contact or a
   parent's phone number, not just the young member's own record).
4. **Area Manager**: no write access to this data at all, despite already
   having broad *read* access to their whole branch. If an Area Manager
   separately also holds a Group Leader assignment for a specific group,
   rule 3 grants them write access there — through that role, not through
   being an Area Manager.
5. **Group Helper**: read-only. No rule grants them write access.

Rules 1, 4, and 5 need nothing beyond what the authorization engine already
supports. Rules 2 and 3 each depend on a piece of infrastructure that
doesn't exist yet — see below. Per this session's decision, **both are
built as prerequisite increments before any contact-data-expansion write
endpoint ships**, rather than shipping a self-service-only version first.

### Prerequisite 1: Main Contact tracking — delivered

Built; see [`reviews/main-contact-tracking.md`](reviews/main-contact-tracking.md)
and `api-contract.md`'s "Main Contact tracking" section. Prerequisites 2
and 3 below are still not started.

Designed in `family-and-directory-design.md` ("Main Contact is the sole
gate to family CRM access... dated and historical, the same way role
assignments are") but never built — `contact_family_units` today is just
`contact_id`, `family_unit_id`, `relationship`, with no Main Contact
concept and no dating at all. A new table, mirroring the dated shape
`contact_roles_groups` already uses:

**`contact_family_main_contacts`**: `family_unit_id`, `contact_id`,
`start_date`, `end_date` (nullable). A partial unique index enforces at
most one current (`end_date IS NULL`) Main Contact per family unit,
matching the existing "exactly one active Group Leader per group" pattern.
Kept as its own table rather than a flag on `contact_family_units`, so
Main Contact history is independently queryable from relationship history
without conflating two different "start/end" concepts on one row.

### Prerequisite 2: Group-Leader-exact-group write scope — delivered

Built; see [`reviews/group-leader-write-scope.md`](reviews/group-leader-write-scope.md)
and `api-contract.md`'s "Write authorization and CSRF" section. Prerequisite
3 below is still not started.

`app/policies/authorization.toml` previously granted `contact:update` (and every
other write action) to Global System Administrator only — confirmed by
inspection, not just the contract text. `open-questions.md` #4 already
flagged an exact-group (not descendant-inclusive) Group Leader write scope
as a "next step" for *basic* contact writes; it has never been built for
any resource. This is genuinely reusable beyond contact-data-expansion, so
it's a prerequisite in its own right: a new policy source (the existing
`group_role` source only supports `group_descendants`/`all` scopes, not
"this exact group, no descendants") plus the query change to
`AuthorizationService` needed to express it.

### Prerequisite 3: group-role-to-family extension — delivered

Built; see [`reviews/group-leader-family-write-extension.md`](reviews/group-leader-family-write-extension.md).
Applied directly to `contact:update` (and, as a necessary consequence,
`contact:view`) rather than left unused — see that review for why. All
three prerequisites are now delivered.

The second half of rule 3 — "and their family members" — is a two-hop
traversal (caller's Group Leader group → members with an active role there
→ those members' family units → every other contact in those units) that
nothing in `AuthorizationService` currently expresses; every existing rule
answers one relationship hop, not two. Built on top of Prerequisite 2
rather than replacing it: prerequisite 2 answers "who's in my exact
group," this extends that set through `contact_family_units`.

## Sensitive-data read access — delivered for emergency contact

Medical conditions and emergency contact get a new, separately-grantable
`contact:view-sensitive` action rather than riding on ordinary
`contact:view` — so a Group Helper who can see a child's name and roles
doesn't automatically see their medical notes or emergency contact.
Resolved during the emergency-contact increment (asked explicitly, since
this section's original wording was ambiguous on the point): it mirrors
`contact:view`'s **entire current rule set**, not just the organisational
roles — Global System Administrator → everyone; Area Manager →
`group_descendants`; Group Leader → `group_descendants` and
`group_and_family`; family `Parent` → `family`; `self` → `self`. A person
can see their own emergency contacts and a parent can see their child's,
consistent with how every other contact-data-expansion category treats
self/family read access, not just organisational roles. Being a separate
action rather than a new rule bolted onto `contact:view` means it can be
tightened further later (for example, requiring a safeguarding-training
flag) without touching ordinary contact visibility. See
[`reviews/emergency-contact-endpoint.md`](reviews/emergency-contact-endpoint.md).

## Still to confirm before writing any contract

1. **Communications preferences exact shape** — confirm channels, defaults,
   and whether `consent_recorded_at` needs to be per-channel rather than
   one shared timestamp, before that category's contract is written.

## Suggested delivery order

Per this session's decision, prerequisites land before any
contact-data-expansion field ships, so the full five-rule write model is
available from the first category rather than a self-service-only version
shipping first:

1. **Main Contact tracking** (Prerequisite 1) — delivered. Self-contained schema and
   read/write endpoints for the concept itself.
2. **Group-Leader-exact-group write scope** (Prerequisite 2) — delivered. Reusable
   beyond this feature; also unblocks the basic-contact-write extension
   `open-questions.md` #4 already anticipated.
3. **Group-role-to-family extension** (Prerequisite 3) — delivered. Built on top of
   (2).
4. **Contact details** (phone/address) — delivered; see
   [`reviews/contact-details-endpoints.md`](reviews/contact-details-endpoints.md).
   The first actual new-data category, with the full write model available
   from day one via two new actions, `contact-phone:update` and
   `contact-address:update`.
5. **Personal details** — delivered; see
   [`reviews/personal-details-endpoint.md`](reviews/personal-details-endpoint.md).
   Trivial schema (five nullable columns on `contacts`), surfaced through
   the existing contact endpoints; a new `contact-personal:update` action
   carries the full write model independently of `contact:update`.
6. **Emergency contact** — delivered; see
   [`reviews/emergency-contact-endpoint.md`](reviews/emergency-contact-endpoint.md).
   Self-contained table, the one hard-delete resource in this system, and
   the first to use the new `contact:view-sensitive` read permission.
7. **Communications preferences**, once its exact shape (the remaining
   open question above) is confirmed.
8. **Medical conditions** last — the largest schema (three tables), and
   the second category to use `contact:view-sensitive` (introduced by
   emergency contact, item 6 above).

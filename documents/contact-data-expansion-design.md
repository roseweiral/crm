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

## Personal details (columns directly on `contacts`)

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

## Emergency contact

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

## Still to confirm before writing any contract

1. **Sensitive-data access control.** Medical conditions (and arguably
   emergency contact) are more sensitive than a name or role assignment.
   Should reading them require a *stricter* permission than ordinary
   `contact:view` — for example, an ordinary Group Helper who can see a
   child's name and roles should not automatically see their medical
   notes? This needs resolving before the medical-conditions increment
   specifically; it doesn't block the personal-details or contact-details
   categories, which carry no more sensitivity than what's already visible
   today.
2. **Communications preferences exact shape** — confirm channels, defaults,
   and whether `consent_recorded_at` needs to be per-channel rather than
   one shared timestamp, before that category's contract is written.
3. **Write-permission scoping for every new category** — who can edit a
   contact's phone numbers, addresses, medical log, emergency contacts, and
   comms preferences (self-service? Main Contact on their family's behalf?
   Group Leader within their group? System Administrator only?) is a
   separate decision per category, not addressed by this session, and
   follows the same "extend the policy matrix before the write endpoint"
   discipline `authorization-architecture.md` already establishes.

## Suggested delivery order

Not a commitment, just a reasonable sequence: **contact details** (phone/
address) first — least sensitive, most broadly useful, and the history
pattern it establishes is reused by nothing else, so it's a clean, fully
self-contained first increment. **Personal details** next — trivial schema,
same low sensitivity. **Emergency contact** next — self-contained, moderate
sensitivity. **Communications preferences** once its exact shape is
confirmed. **Medical conditions** last, once the sensitive-data access
question is resolved — it's the largest schema (three tables) and the one
increment that can't start until an open question above is answered.

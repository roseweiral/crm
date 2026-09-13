# Family relationships and organisation directory

## Status

This records the agreed decisions from a design session working through
[open questions](open-questions.md) #3 and #7. These are agreed decisions, not
yet implemented. Each becomes its own increment through the normal
[way of working](way-of-working.md) — contract update, TDD, implementation,
review — and the address book increment starts at the database layer before
any endpoint or contract work, per the note below.

## Young Member group membership

Nothing today links a child directly to a Group; role types are currently
Group Leader, Group Helper, and Area Manager only, and demo data deliberately
never gives children an organisational role. That gap is now closed:

- A new role type, **Young Member**, links a child to a specific Group.
- A young member's group membership uses `contact_roles_groups` the same way
  adult roles do — same table, `start_date`/`end_date`, evaluated at request
  time the same way.
- An adult does not gain any group-structure link merely because their child
  holds a Young Member assignment. An adult appears in the org structure only
  through their own role assignment.
- `demo-data.md`'s current rule ("Generated children never receive
  organisational roles") will need to change once this is implemented.

## Multiple roles and overlap rules

- An adult may hold any number of concurrent role assignments, across
  different groups and role types, with no upper limit — for example,
  simultaneously Group Leader of one group, Area Manager of another, and
  Group Helper of a third.
- Exactly one active Group Leader per group at a time: overlapping active
  assignments of role type Group Leader for the same group are not allowed.
- **Still to confirm:** does that same one-at-a-time rule extend to Area
  Manager, or can several people hold Area Manager for the same group/level
  concurrently, the way Group Helper already allows multiple concurrent
  people? Confirm before writing the contract for this increment.

## Organisation-wide address book ("GAL")

A new feature, distinct from the existing group-hierarchy read scoping (which
is unchanged). It also resolves open question #3's cross-branch case: rather
than extending hierarchical scope across branches, visibility of someone
outside your own branch now happens entirely through the address book's own
opt-out sharing model instead of through `AuthorizationService.scope()`.

- Every adult contact holding an active *adult* organisational role (Group
  Leader, Group Helper, Area Manager, Global System Administrator) is
  discoverable in the address book, by default, to every other such adult
  across the whole organisation — regardless of group or branch.
- Young Member and parent-only contacts are never included. (May be
  revisited if a future "Young Leader" role is introduced.)
- An adult can hide themselves from the address book entirely.
- An adult can hide individual roles from the address book while remaining
  visible for their other, non-hidden roles.
- The one exception to both opt-outs: nobody can hide themselves, or a role,
  from their own organisational leadership. Anyone with hierarchy-based scope
  over them via the group tree always sees them regardless of address-book
  settings — hierarchical visibility always wins over an address-book opt-out.
- Address book entries show: name, contact details, roles held (excluding any
  the person has hidden), and their position in the org structure.
- Skills (so members become searchable by skill) and a profile photo are
  explicit future-vision items, deliberately deferred out of v1. The schema
  should leave room for adding them later without a breaking migration, but
  neither is built now.
- This increment starts at the database layer: it needs new
  visibility-preference data (a per-contact "hidden from address book" flag,
  and per-role-assignment visibility) before any endpoint or contract work.

## Family relationships and Main Contact

- A family unit stays a single, persistent record — "at least for now" —
  rather than splitting into multiple units when a family's structure changes
  (divorce, fostering, remarriage). Relationships within it change over time
  via dates, not by moving people into a new family unit.
- `contact_family_units.relationship` becomes a larger enum rather than a
  pairwise contact-to-contact relationship. Chosen deliberately over a more
  precise pairwise model because it is much simpler to administer and build.
  Exact enum values (Mother, Father, Guardian, Step, Aunt, Uncle, Foster
  Parent, Child, and so on) are to be finalized when this contract is
  written.
- Every relationship row gets a `start_date` and an `end_date`, mirroring
  `contact_roles_groups`. Start defaults to when the relationship is created
  but can be set to a future date; `end_date` is null while active.
- Exactly one Main Contact per family unit at any point in time. Any adult
  relationship type in the family is eligible to become Main Contact — not
  limited to Mother/Father — confirmed via the foster-care scenario below.
- **Main Contact is the sole gate to family CRM access.** For now, only the
  current Main Contact can log in and see the family's information; every
  other adult connected to the family unit — including a non-main Mother or
  Father — has no CRM login or visibility, regardless of their relationship
  type. This is a deliberate simplification: known edge cases exist (for
  example, two actively involved parents who both want visibility) and are
  explicitly deferred for later revisit, not solved now.
- Main Contact status is itself dated and historical, the same way role
  assignments are: the system must be able to show who was Main Contact at
  any point in time, not only who is Main Contact now.
- When Main Contact changes hands — for example a safeguarding-driven
  reassignment to a Foster Parent because the birth parents "lose capacity" —
  the outgoing Main Contact is locked out: they lose login and visibility at
  the same moment as the handover. This mirrors the existing contact-writes
  precedent, where archiving a contact revokes its sessions in the same
  transaction; a Main Contact change should likely revoke the outgoing Main
  Contact's sessions the same way.
- Aunt, Uncle, and other non-parental relationship types never log in or gain
  family visibility on their own — consistent with Main Contact in practice
  being assigned to a parent/guardian/foster-parent figure, even though
  nothing in the data model itself restricts eligibility.

## Still to confirm before writing the contract

1. Does the Group Leader one-at-a-time rule extend to Area Manager?
2. The exact relationship-type enum values.

Everything else above is an agreed decision, ready to carry into stage 1
(contract update) of the relevant increment.

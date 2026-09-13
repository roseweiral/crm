# Open questions

A tracked list of design decisions raised in [`AnadA.md`](AnadA.md#open-questions)
and [`authorization-architecture.md`](authorization-architecture.md). Numbers
match `AnadA.md`'s original "Open questions" list so the two stay
cross-referable. Resolved items below are agreed decisions; where a decision
changes behavior, it still has to go through the normal
[way of working](way-of-working.md) — contract update, TDD, implementation,
review — before it's live. Recording it here is stage zero, not stage three.

## Resolved decisions

| # | Question | Decision | Next step |
| --- | --- | --- | --- |
| 1 | Which organisation owns the CRM, and do most intended users have managed Google Workspace or Microsoft 365 accounts? | Personal/mixed accounts — no shared organisational tenant. No Google Workspace or Microsoft 365 domain restriction is planned; provider configuration stays as-is (open to any Google/Microsoft account holder, still invitation-gated). | None needed now. Revisit only if the organisation later adopts a managed tenant. |
| 2 | Are there cases where a descendant group must be excluded from an otherwise inherited parent-group assignment? | No. A role assignment on a group always includes every descendant group, with no carve-outs. | None — this confirms current behavior in [`authorization-architecture.md`](authorization-architecture.md). |
| 3 | Precisely which resources belong to a group, particularly contacts with roles in multiple groups and family members spanning group boundaries? | Resolved through a design session — see [`family-and-directory-design.md`](family-and-directory-design.md). Highlights: a new Young Member role links children to a Group; adults may hold unlimited concurrent role assignments; cross-branch visibility of an out-of-scope person is handled by a new organisation-wide address book with its own opt-out model, not by extending hierarchical scope. | Two details still need confirming before the contract is written — see that document's "Still to confirm" section. Then: contract update, TDD, implementation, review, starting at the database layer for the address book. |
| 4 | Are Group Leader and Area Manager initially read-only, or will either role receive write permissions? | **Group Leader**: full Read/Write/Archive over contacts and role/group assignments within their *exact assigned group only* — not descendant groups. The group record itself (rename/move/create) stays Global-System-Administrator-only. **Area Manager**: stays read-only over all contacts/assets linked to their assigned group and its descendants (unchanged). "Delete" means the existing archive/status-change pattern, never hard deletion — consistent with the contact-writes contract's explicit exclusion of hard deletion. | Feeds the permission catalogue in [`authorization-architecture.md`](authorization-architecture.md) ("Required policy work"). Write it into `api-contract.md` as its own increment when Group Leader writes are next up. |
| 5 | What audited recovery process should be available if all system administrators lose access? | Manual, documented operator procedure: a trusted operator with server/DB access runs a recovery script modeled on `bootstrap_admin.py` to create a new admin invitation, writing a mandatory audit event. No new API endpoint for this in the current release. | Write the runbook into [`authentication-operations.md`](authentication-operations.md) "First administrator and invitations" when this is built. |
| 6 | If an invited contact has no email address yet, should creating the invitation also update the contact's email? | Yes — invitation creation may also set the contact's email in the same request/transaction when the contact doesn't already have one. | Exact validation/conflict rules (e.g. contact already has a *different* email) to be specified in `api-contract.md` when the invitations-write increment reaches stage 1. |
| 7 | Does a `guardian` family relationship receive the same access as `parent`? | Resolved through the same design session — see [`family-and-directory-design.md`](family-and-directory-design.md). The relationship taxonomy is expanded (Mother, Father, Guardian, Step, Aunt, Uncle, Foster Parent, ...) as a bigger enum, not a pairwise model. Family CRM access is now gated entirely by a single, dated **Main Contact** role per family unit — any adult relationship type is eligible, but only the current Main Contact can log in and see the family, a deliberate simplification with known edge cases deferred. | Finalize the exact enum values, then write the family-writes contract when that increment starts. |
| 8 | When a child becomes an adult, should family visibility change automatically? | No automatic change. Family visibility depends only on the `family_unit` relationship, not age — contacts don't need a stored date of birth for this. | None — confirms the assumption already implicit in `authorization-architecture.md`. |
| 9 | Does the 12-hour session expire absolutely, or may active use renew it? | Replace the single fixed 12-hour `expires_at` with a sliding session: an idle timeout after **1 hour of no activity**, and an absolute cap of **24 hours since login** regardless of activity, whichever comes first. | Its own increment through the normal 4-stage cycle: contract update to `authentication-operations.md`, then TDD using backdated `created_at`/last-activity timestamps (the same technique `test_authentication_lifecycle.py` already uses — no real waiting, no exception to testing was granted), then implementation, then review. |

All nine original open questions are now resolved. Two implementation-level
details remain (see `family-and-directory-design.md`'s "Still to confirm")
and each resolved decision still needs its stage-1 contract write-up before
implementation — see "Next step" above and [`way-of-working.md`](way-of-working.md).

## Related pending design work

Not phrased as questions in the source documents, but blocking in the same way:

- **Permission catalogue and write-operation matrix** — Q4's resolution above gives
  the first concrete answers (`contact:update` / `role:assign` scoped to a Group
  Leader's exact group; read-only descendant scope for Area Manager). The
  address book (Q3) adds a new kind of permission entirely — organisation-wide
  visibility gated by self-service opt-out rather than hierarchy. The
  remaining catalogue entries (`family:update`, `membership:manage`,
  `invitation:create` scoping, general `role:assign` rules) are still open
  ([`authorization-architecture.md`](authorization-architecture.md) "Required policy work").
- **Following API increments** — family membership writes, role/group assignment
  writes, group creation/editing, reference-data writes, and invitation
  listing/revocation are all listed as design-pending
  ([`api-contract.md`](api-contract.md) "Following increments").
- **Security-consistency follow-up** — migrate the invitation and sign-out
  endpoints onto the same Origin/CSRF write protection used by contact writes
  ([`reviews/contact-writes.md`](reviews/contact-writes.md)).

## Using this list

Each new API increment follows `api-contract.md`'s documentation → failing tests
→ implementation → review cycle. Before starting one, check both tables above:
a resolved decision still needs to be written into the relevant contract at
stage 1; an open question needs resolving first, either directly in this file
or in the design document it points back to.

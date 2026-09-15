# Group-Leader-exact-group write scope review

## Delivered scope

A current Group Leader may now `PATCH` (full field access, including
archiving) any contact holding an active role in their *exact* assigned
group — not descendant groups. Resolves
[open-questions.md](../open-questions.md) #4's long-pending "next step."
`contact:create` is unaffected — remains Global-System-Administrator-only.
Contract: `documents/api-contract.md` "Write authorization and CSRF".
Design rationale: `documents/contact-data-expansion-design.md`
(Prerequisite 2). Executable coverage: new cases in
`tests/api/test_contact_writes.py`.

New, reusable authorization-engine capability, not a one-off: `group_role`
sources can now be scoped `"group"` (the caller's exact assigned group,
computed without `groups_by_role`'s descendant-walking recursion) alongside
the existing `"group_descendants"`/`"all"`. `contact-data-expansion-design.md`'s
Prerequisite 3 (Group Leader write access extended to their group's
members' family units) builds on this same `exact_groups_by_role` property
rather than introducing a separate mechanism.

## TDD evidence

- 7 new cases added to `test_contact_writes.py`, confirmed red before
  implementation: the two "Group Leader can write within their exact
  group" cases failed for the right reason (403, scope didn't exist yet);
  the five "cannot" cases (descendant group, unrelated group, contact
  creation, Area Manager, Group Helper) passed immediately even before
  implementation — expected, since they assert today's already-correct
  restrictive behavior continues to hold, not new behavior.
- After implementation: 245 tests pass (up from 238), both on a fresh
  database and repeated without a reset. No existing test needed
  adjustment — this is a pure scope *addition* to an action that was
  previously admin-only-full-stop.

## Review notes (no code changes required)

1. **New pathway to an already-fixed hazard class, confirmed safe by
   construction, not re-tested.** A Group Leader can now write to (and
   archive) their own contact record if they hold their own role in the
   group they lead — the same "caller archives themselves" shape the
   contact-writes review's concurrent-self-archive deadlock fix already
   protects against
   (`test_self_archive_does_not_deadlock_concurrent_sessions`). That fix —
   session-activity updates committing in a short, independent transaction
   before the resource handler takes any contact lock — operates entirely
   at the session/authentication layer and has no dependency on *which*
   authorization rule granted the write. This change only touches scope
   computation in `AuthorizationService`, nothing in the session-locking
   path, so the existing protection covers this new caller type by
   construction. Not duplicated as a new test: doing so would re-test the
   generic mechanism, not anything specific to Group Leader.
2. **Rule ordering in the policy engine confirmed order-independent for
   correctness.** `scope()`'s loop unions every matching rule's permitted
   ids regardless of order; only the `unrestricted` short-circuit (an
   `"all"`-scoped match) is an early return, and that was already true
   before this change. Adding the new `"group"` branch doesn't introduce an
   ordering dependency between it and the existing Global-System-Administrator
   rule on `contact:update`.

## Deployment and operational limits

No schema or migration — this is a policy (`authorization.toml`) and
authorization-engine (`app/authorization.py`) change only. Once deployed,
every current Group Leader immediately gains write access to contacts in
their own exact group; no rollout flag or gradual enablement, matching how
every other policy change in this project has shipped so far (no live
system yet). Prerequisite 3 (Group Leader write access extended to their
group's members' family units) remains a separate, not-yet-started
increment on top of this one.

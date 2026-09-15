# Group-role-to-family write extension review

## Delivered scope

Extends the Group-Leader-exact-group write scope
(`reviews/group-leader-write-scope.md`) through `contact_family_units`: a
Group Leader can now also update (full field access, including archiving)
every contact sharing a family unit with one of their group's members —
any relationship type, not only `parent`. Applied to the existing
`contact:update` action directly, per this session's decision, rather than
left unused until a future contact-data-expansion category ships.
`contact:view` gained the matching extension, additive to its existing
`group_descendants` rule, because it turned out to be a hard prerequisite,
not an independent choice — see below. Contract:
`documents/api-contract.md` "Write authorization and CSRF". Design
rationale: `documents/contact-data-expansion-design.md` (Prerequisite 3).
Executable coverage: new cases in `tests/api/test_contact_writes.py`.

## TDD evidence

- 4 new cases, confirmed red before implementation for two different
  reasons across two implementation attempts:
  - First red pass: the two "can update a family member" cases failed
    because the read side wasn't wired up yet — the test helper that
    fetches an ETag (a prerequisite for any PATCH) got a `404` from `GET`,
    since `contact:view` didn't reach family members at all.
  - After adding the `contact:view` extension and rerunning: the same two
    cases *still* failed, now with `403` on the `PATCH` itself — because
    `contact:update`'s Group Leader rule hadn't actually been switched from
    `scope = "group"` to `scope = "group_and_family"` yet, despite the
    contract text already describing that it should be. A real
    implementation gap, not a test issue — see below.
  - The two "cannot" cases (unrelated contact's family, everything from
    Prerequisite 2's tests) passed throughout, correctly asserting
    behavior that was never meant to change.
- After both fixes: 248 tests pass (up from 245), both on a fresh database
  and repeated without a reset.

## Issues found and fixed

1. **The read-side dependency wasn't obvious until red proved it.** A
   write-only scope extension is unusable through this API's GET-then-PATCH
   ETag pattern, since obtaining `If-Match` requires a prior successful
   `GET`. This surfaced as a test failure, not something reasoned out in
   advance — exactly what running the contract tests red is for. Fixed by
   adding the same `group_and_family` rule to `contact:view`, additive to
   its existing `group_descendants` rule, which is otherwise unchanged.
2. **`contact:update`'s policy rule was described in the contract before it
   was actually written.** The contract update said Group Leader's
   `contact:update` rule uses `group_and_family`; the TOML edit that would
   make that true was missed in the same pass — the authorization *engine*
   gained the capability, and `contact:view` was correctly wired, but
   `contact:update` itself was left on the older `scope = "group"` from
   Prerequisite 2. Caught immediately by the still-red tests rather than
   silently shipping a contract that didn't match the code. Fixed by
   updating the existing rule in place.

## Review notes

1. **Deliberately includes non-parent family members** — a sibling of a
   group member becomes writable by the Group Leader even if that sibling
   holds no role anywhere and has no connection to the group leader beyond
   sharing a family unit with someone who does. Matches "family members",
   not "parents", from `contact-data-expansion-design.md`'s rule 3
   verbatim, and the SQL has no relationship-type filter to that effect.
   Calling this out explicitly as an intentional, tested characteristic
   (`test_group_leader_can_update_a_non_parent_family_member_too`), not an
   incidental side effect someone should "fix" later.
2. **`contact:view`'s extension is scoped to the exact group** (`group_and_family`,
   not `group_descendants_and_family`) even though the *rest* of
   `contact:view`'s Group Leader access already reaches descendant groups.
   Intentional: the family extension exists to serve the write scope, which
   Prerequisite 2 deliberately restricted to the exact group per
   `open-questions.md` #4; extending family-reach to descendant-group
   members as well was never asked for and would be a bigger, un-agreed
   grant.
3. Self-write and deadlock reasoning from `reviews/group-leader-write-scope.md`
   carries over unchanged: this only changes which contacts are in scope,
   not the session-locking path, so no new review needed there.

## Deployment and operational limits

No schema or migration — policy and authorization-engine change only,
same as Prerequisite 2. All three prerequisites from
`contact-data-expansion-design.md` are now delivered; the first actual new
data category (contact details: phone/address) can start from a full,
tested write model on day one, as planned.

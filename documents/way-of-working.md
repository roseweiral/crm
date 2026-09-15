# Way of working: feature increments

## Purpose

This is the agreed cycle for building each new feature increment, backend
through frontend, as one flowing sequence rather than two separately-run
halves:

1. Agree the deliverable
2. Update contracts
3. Write API tests
4. Implement
5. Review
6. Documentation
7. Write frontend tests
8. Implement
9. Review
10. Document
11. Confirm all tests pass

Steps 1–5 formalize what `api-contract.md` already states in brief
("documentation → failing tests → implementation → review") and what
`reviews/contact-writes.md` demonstrates as a worked example. Steps 6–10
extend the same discipline to the frontend that consumes it —
`reviews/address-book.md` is steps 1–5's most recent worked example; its
frontend pass is steps 6–10's first.

Run the full cycle once per feature increment. Do not batch several
unrelated resources through one pass; `api-contract.md` deliberately scopes
"the first increment" to contact POST/PATCH alone and defers the rest for
the same reason. A feature can pause after step 5 — reviewed and shipped on
the API, with its frontend picked up later, the way the address book's API
landed before its screens did — but once a frontend pass does start, it runs
steps 6–10 in full, not just an implementation step tacked onto the end.

## Before starting: check open questions

Check [`open-questions.md`](open-questions.md) for anything the increment
depends on. If a relevant question is still Open, either resolve it there
first or record, in the deliverable or contract, the explicit assumption
you are proceeding under. Silently assuming an answer is how inconsistent
authorization rules creep in. This applies at any step, not only step 1.

## 1. Agree the deliverable

- Before editing any contract, agree in plain terms what this increment
  delivers and why — the scope boundary for this one pass through the
  cycle, and what's explicitly deferred. This can be as lightweight as an
  agreed plan; it doesn't need its own permanent document.
- Check the open questions above as part of this. A resolved decision still
  needs writing into the relevant contract at step 2 — recording a decision
  in `open-questions.md` is stage zero, not a substitute for it.

## 2. Update contracts

- Edit [`api-contract.md`](api-contract.md) (or the relevant design document)
  first: request/response shapes, validation rules, status codes,
  authorization rules, and transactional/audit behavior, described precisely
  enough that tests can be written directly from it.
- Contract changes go through the same review as code — opened as a pull
  request, reviewed by the automated reviewer
  ([`automated-pr-review.md`](automated-pr-review.md)) and/or a human — before
  any test is written against it.
- Do not implement behavior the contract doesn't describe yet. Extend the
  contract before extending the code.
- When an increment changes the database schema, update
  [`database/db.dbml`](database/db.dbml) at this stage too. It is the
  source of truth for the schema — `database/schema.sql` is not. Agree
  the model in DBML before any migration or `schema.sql` change is
  written.

## 3. Write API tests

- Add executable tests under `tests/api/` directly from the agreed contract,
  marked with the appropriate pytest category (`smoke`, `contract`, or
  `regression` — see [`tests/README.md`](../tests/README.md)).
- Run the new tests alone and confirm each one fails for the intended reason —
  a missing route, the wrong status code — rather than an unavailable service
  or a broken fixture. This check is explicit in `tests/README.md`'s TDD
  workflow and is worth doing before assuming "red" means what you think it
  means. A test that passes red for the wrong reason (a filter parameter
  that's silently ignored, say) isn't proving anything — strengthen it until
  it fails for real before trusting it as a baseline.
- Record the red baseline (test count, failure reasons) the way
  `reviews/contact-writes.md` does, so step 5 has real before/after evidence.

## 4. Implement

- Make the smallest implementation change that turns the new tests green
  without breaking the existing suite.
- Keep authorization and hierarchy/family-traversal logic inside the shared
  `AuthorizationService` (see [`authorization-architecture.md`](authorization-architecture.md))
  rather than duplicating rules per router.
- Run the complete API suite — not just the new tests — before moving to
  review.
- Bring `database/schema.sql` into line with the already-agreed `db.dbml`.
  Never edit the schema first and update DBML as an afterthought.
- There is no live system yet: every environment is built fresh from
  `schema.sql` plus demo/seed data, so a schema change is made directly in
  `schema.sql` rather than through a migration under `database/migrations/`.
  Start writing migrations once a real database exists that has to keep its
  data across a schema change — `database/migrations/README.md` and its one
  existing example show the shape that will take.

## 5. Review

- Review the diff for security, transactional correctness, and consistency
  with existing endpoints: authentication, CSRF, audit logging, and
  concurrency handling are the categories that actually turned up issues in
  the contact-writes review.
- Any issue the review finds becomes a new regression test before it becomes
  a fix — never a silent correction. The contact-writes review is the
  template: it named three additional failures and left each one with a
  passing regression test. The address-book review found and fixed a fourth
  kind of issue the same way: implementation validation looser than the
  documented contract, pinned down with a regression test before the fix.
- Re-run the full API suite before moving on.

## 6. Documentation

- Write the API-side review document under `documents/reviews/<increment>.md`
  covering: delivered scope, TDD evidence (red/green counts), issues the
  review caught, prioritized follow-up items, and any deployment or
  migration steps — following the shape of
  [`reviews/contact-writes.md`](reviews/contact-writes.md) and
  [`reviews/address-book.md`](reviews/address-book.md). A small follow-on
  addition to an already-reviewed endpoint (the address book's `group_id`
  filter, for example) can be a short addendum to the existing review doc
  instead of a new one.
- Update [`open-questions.md`](open-questions.md) if the increment resolved,
  narrowed, or surfaced an open question.
- If this increment has a frontend, this is also where its UI documentation
  gets written: the screens, routes, and states (loading, empty, error,
  permission-denied) it needs, and which API calls each screen makes. This
  is the frontend's equivalent of step 2's contract — precise enough that
  step 7's tests can be written directly from it — and it's what step 7
  gets written against. It lives in [`web/README.md`](../web/README.md) (or
  a short document under `documents/` if a feature's screens outgrow a
  README section), not in `api-contract.md`, which stays API-only. Do not
  build UI behavior this document doesn't describe yet, mirroring step 2's
  "extend the contract before extending the code" rule.

## 7. Write frontend tests

- Add Playwright specs under `tests/e2e/specs/` directly from step 6's UI
  documentation.
- Run the new specs alone and confirm each fails for the intended reason —
  a missing route or element — rather than a broken test harness or a
  missing signed-in session fixture. Same discipline as step 3, applied to
  the browser layer.

## 8. Implement

- Make the smallest implementation change that turns the new specs green
  without breaking the existing suite.
- Reuse existing frontend conventions (the `services/api.ts` request
  pattern, existing component/page structure, the established CSS) rather
  than introducing a parallel style or pattern for one screen.
- Never re-derive an authorization decision in the frontend that the API
  already enforces. The UI may hide an unavailable action for usability
  (`authorization-architecture.md`), but a second, independent copy of an
  eligibility rule is exactly the kind of drift step 5 (and its follow-ups
  in `reviews/address-book.md`) warns about — handle a `403` as a screen
  state instead.
- Run the complete e2e suite — not just the new specs — before moving to
  review.

## 9. Review

- Review the diff for the same categories step 5 covers, adapted to the
  frontend: accessibility, error/empty/permission-denied states, and
  consistency with existing screens and the API client.
- Any issue the review finds becomes a new e2e (or component) regression
  test before it becomes a fix, same rule as step 5.
- Re-run the full e2e suite before moving on.

## 10. Document

- Write a short review document under
  `documents/reviews/<increment>-frontend.md`, following the same shape as
  step 6's review doc: delivered scope, e2e red/green evidence, issues
  found and fixed, follow-ups, deployment notes.
- Update `web/README.md` to reflect what actually shipped.
- Update [`open-questions.md`](open-questions.md) if the frontend pass
  resolved, narrowed, or surfaced an open question.

## 11. Confirm all tests pass

- Run the complete API suite twice, including once without a database
  reset (see the repeatability check in `tests/README.md`), against the
  final diff.
- Run the complete e2e suite against the final diff.
- Only call the increment done once both are green together — this is the
  closing gate for the whole cycle, not a repeat of the lighter in-stage
  checks steps 4, 5, 8, and 9 already do along the way.

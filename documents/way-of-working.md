# Way of working: API increments

## Purpose

This is the agreed four-stage cycle for building each new endpoint or resource
increment. It formalizes what `api-contract.md` already states in brief
("documentation → failing tests → implementation → review") and what
`reviews/contact-writes.md` demonstrates as a worked example. Every future
increment — family writes, role/group assignment writes, group management,
reference-data writes, invitation management — follows this cycle.

Run the full cycle once per resource or behavior increment. Do not batch
several unrelated resources through one pass of stages 1–4; `api-contract.md`
deliberately scopes "the first increment" to contact POST/PATCH alone and
defers the rest for the same reason.

## Before starting: check open questions

Check [`open-questions.md`](open-questions.md) for anything the increment
depends on. If a relevant question is still Open, either resolve it there
first or record, in the contract you are about to write, the explicit
assumption you are proceeding under. Silently assuming an answer is how
inconsistent authorization rules creep in.

## 1. Agree / update the contract

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

## 2. Create tests using TDD

- Add executable tests under `tests/api/` directly from the agreed contract,
  marked with the appropriate pytest category (`smoke`, `contract`, or
  `regression` — see [`tests/README.md`](../tests/README.md)).
- Run the new tests alone and confirm each one fails for the intended reason —
  a missing route, the wrong status code — rather than an unavailable service
  or a broken fixture. This check is explicit in `tests/README.md`'s TDD
  workflow and is worth doing before assuming "red" means what you think it
  means.
- Record the red baseline (test count, failure reasons) the way
  `reviews/contact-writes.md` does, so stage 4 has real before/after evidence.

## 3. Develop the endpoint to pass the tests

- Make the smallest implementation change that turns the new tests green
  without breaking the existing suite.
- Keep authorization and hierarchy/family-traversal logic inside the shared
  `AuthorizationService` (see [`authorization-architecture.md`](authorization-architecture.md))
  rather than duplicating rules per router.
- Run the complete suite — not just the new tests — before moving to review.
- Bring `database/schema.sql` into line with the already-agreed `db.dbml`.
  Never edit the schema first and update DBML as an afterthought.
- There is no live system yet: every environment is built fresh from
  `schema.sql` plus demo/seed data, so a schema change is made directly in
  `schema.sql` rather than through a migration under `database/migrations/`.
  Start writing migrations once a real database exists that has to keep its
  data across a schema change — `database/migrations/README.md` and its one
  existing example show the shape that will take.

## 4. Review and retest

- Review the diff for security, transactional correctness, and consistency
  with existing endpoints: authentication, CSRF, audit logging, and
  concurrency handling are the categories that actually turned up issues in
  the contact-writes review.
- Any issue the review finds becomes a new regression test before it becomes
  a fix — never a silent correction. The contact-writes review is the
  template: it named three additional failures and left each one with a
  passing regression test.
- Write a short review document under `documents/reviews/<increment>.md`
  covering: delivered scope, TDD evidence (red/green counts), issues the
  review caught, prioritized follow-up items, and any deployment or migration
  steps — following the shape of
  [`reviews/contact-writes.md`](reviews/contact-writes.md).
- Re-run the full suite twice, including once without a database reset (see
  the repeatability check in `tests/README.md`), before calling the increment
  done.
- Update [`open-questions.md`](open-questions.md) if the increment resolved,
  narrowed, or surfaced an open question.

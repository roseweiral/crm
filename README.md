# Volunteer CRM

A CRM for managing volunteers, young members, families, organisational groups,
roles, and awards. See the [project overview](documents/project-overview.md) for
the full vision, architecture, and technology choices.

## Documentation index

Docs are grouped by topic so an agent or new contributor can jump straight to
the relevant one instead of reading the whole tree.

### Architecture and process

| Document | Covers |
| --- | --- |
| [Project overview](documents/project-overview.md) | Vision, repository structure, technology choices, containers, environments |
| [Way of working](documents/way-of-working.md) | The 11-step cycle used for every feature increment: deliverable → contract → API tests → implement → review → documentation → frontend tests → implement → review → document → confirm all tests pass |
| [Open questions](documents/open-questions.md) | Tracked list of design decisions, resolved and still-open, blocking future increments |
| [Family and directory design](documents/family-and-directory-design.md) | Agreed decisions on Young Member roles, the organisation-wide address book, and family relationships/Main Contact |
| [Automated PR review](documents/automated-pr-review.md) | The Claude Code Action that reviews pull requests, and the required repository secret |

### Authentication and authorization

| Document | Covers |
| --- | --- |
| [AuthN/AuthZ design (AnadA)](documents/AnadA.md) | Original design decisions, agreed principles, and the source open questions for sign-in and permissions |
| [Authorization architecture](documents/authorization-architecture.md) | The PostgreSQL/policy boundary, `AuthorizationService`, and the planned OpenFGA migration path |
| [Authentication operations](documents/authentication-operations.md) | Implemented OIDC flow, session/invitation lifetimes, bootstrap admin, fake-OIDC service |

### API and testing

| Document | Covers |
| --- | --- |
| [API contract](documents/api-contract.md) | The behavioral specification for each endpoint increment; source of truth for write behavior |
| [Contact-writes review](documents/reviews/contact-writes.md) | TDD evidence and follow-up findings from the first write increment |
| [Address-book review](documents/reviews/address-book.md) | TDD evidence and follow-up findings from the organisation-wide address book increment |
| [Address-book frontend review](documents/reviews/address-book-frontend.md) | TDD evidence, the same-site cookie fix, and follow-up findings from the address book's frontend increment |
| [Documentation browser review](documents/reviews/documents-endpoint.md) | TDD evidence and follow-up findings from the in-app documentation browser's API increment |
| [Documentation browser frontend review](documents/reviews/documents-frontend.md) | TDD evidence and follow-up findings from the documentation browser's frontend increment |
| [Tests README](tests/README.md) | Test categories, the TDD workflow, and how to run focused test selections |
| [Test fixtures](tests/fixtures/README.md) | Where reusable test inputs live |
| [App README](app/README.md) | FastAPI application entry points |
| [Web README](web/README.md) | React/Vite frontend |

### Data

| Document | Covers |
| --- | --- |
| [Database schema (DBML)](documents/database/db.dbml) | Visual/conceptual database model, kept in sync with `database/schema.sql` |
| [Demo data design](documents/demo-data.md) | Faker-based generator rules, record counts, hierarchy, role logic |
| [Seed data](database/seed/README.md) | Deterministic CSVs used to initialise a blank database |
| [Database migrations](database/migrations/README.md) | How to apply migrations to an existing database |
| [Demo data generators](database/demo/README.md) | One generator module per table |

### Deployment

| Document | Covers |
| --- | --- |
| [Internet-facing test deployment](documents/test-deployment.md) | Public demo/acceptance-test environment, Caddy gate, deploy workflow |
| [Hetzner Terraform module](infrastructure/terraform/README.md) | Provisions the test server, public addresses, firewall, SSH access, and Docker host bootstrap |

## Local environment

The Docker Compose environment contains four application services and two on-demand
test services:

- `database`: the disposable PostgreSQL database
- `app`: the FastAPI application
- `frontend`: the React development server
- `fake-oidc`: the development/test OpenID Connect provider
- `api-tester`: pytest API and PostgreSQL tests
- `e2e-tester`: Playwright browser tests
- `e2e-report`: persistent local Playwright HTML report viewer

Docker Compose reads the untracked `.env` file by default. This repository's local
file is configured with `APP_ENV=development`.

Start the application:

```shell
docker compose up --build
```

Run the API tests:

```shell
docker compose run --rm --build api-tester
```

The configured categories run in order and stop on the first failing category.
The default sequence is `smoke,contract,regression`. See
[`tests/README.md`](tests/README.md) for category details and selection options.

Run the browser tests:

```shell
docker compose run --rm e2e-tester
```

Import the CSV seed data:

```shell
docker compose run --rm app python /database/import_seed.py
```

Generate demo data in the development database:

```shell
docker compose run --rm app python /database/demo_data.py --replace
```

Generate reviewable CSV files instead:

```shell
docker compose run --rm app python /database/demo_data.py --output csv
```

Stop the services while retaining database data:

```shell
docker compose down
```

Delete the database and frontend dependency volumes for a completely fresh start:

```shell
docker compose down --volumes
```

When PostgreSQL starts with a new development or test database volume, it automatically
applies the schema and then imports every seed CSV. Existing volumes are left alone.
The API tester also invokes the demo-data runner before executing the tests.

## Environment configuration

Committed example files document the expected settings:

- `.env.example`: local development template
- `.env.test.example`: future test-environment template
- `.env.production.example`: future production template

The internet-facing test infrastructure is configured but has not been provisioned.
Production remains configuration scaffolding only. Copy the relevant example to
an ignored environment file and select it explicitly:

```shell
docker compose --env-file .env.test up
docker compose --env-file .env.production up
```

The environment name is included in the Compose project name, keeping its containers,
network, and volumes separate from other environments.

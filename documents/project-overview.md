# Volunteer CRM project overview

## Project vision

The Volunteer CRM is intended to give a volunteer organisation one coherent place
to manage its people, organisational structure, family relationships, volunteer
roles, and member awards.

The organisation includes both adult volunteers and young members. Contacts can be
connected through anonymous family units without assuming a shared surname or a
traditional family structure. Organisational groups form a hierarchy such as:

```text
HQ
└── County
    └── City
        └── Town
            └── Group
```

Contacts can hold different roles in different groups over defined periods. Award
records preserve nomination and presentation history. The longer-term product will
identify signed-in users and restrict information and actions according to their
permissions and place in the organisation. Authentication now uses invitation-only
Google or Microsoft OpenID Connect sign-in. Authorization scopes reads through
explicit access roles, the organisational hierarchy, and family relationships.

Development follows test-driven development: define the expected behavior in a
failing test, implement the smallest useful change, and then confirm the suite is
green.

## Repository structure

```text
crm/
├── .github/workflows/   Pull-request automation
├── app/                 FastAPI application
├── database/            PostgreSQL creation and data tooling
├── documents/           Architecture and project documentation
├── tests/
│   ├── api/             Pytest API and database tests
│   ├── e2e/             Playwright browser tests
│   └── fixtures/        Reusable test inputs
├── web/                 React web application
├── compose.yaml         Local container orchestration
└── .env.example         Development environment template
```

### Application API

The `app/` directory contains the FastAPI service:

- `main.py` creates the application and registers routers.
- `database.py` provides request-scoped PostgreSQL connections.
- `models/` contains Pydantic API models.
- `routers/` contains versioned HTTP endpoints.

Routes live beneath `/api/v1`. The authenticated read-only API serves contacts, family
units, role types, group types, groups, and contact role/group assignments through
paginated collection and individual detail endpoints.

FastAPI owns the OIDC callback and exchanges provider identities for revocable,
server-side CRM sessions. Provider tokens are never stored in the browser. Health and
authentication entry points remain public; CRM data endpoints require a session.

### Database

The `database/` directory contains everything required to create and populate
PostgreSQL:

- `schema.sql` is the executable PostgreSQL schema.
- `Dockerfile` packages the schema and seed initialization into the database image.
- `init/` contains first-run database initialization scripts.
- `seed/` contains deterministic CSV data intended to initialize a blank database.
- `generated/` contains reviewable CSV output produced by the demo generator.
- `demo/` contains one Python generation module per table.
- `demo_data.py` coordinates Faker generation and database or CSV output.
- `import_seed.py` validates and imports curated seed CSVs.

The database uses UUIDs for every primary and foreign key. PostgreSQL generates
UUIDs for normal application records, while demo records use deterministic UUIDs
so the same generator options produce stable relationships.

### Architecture documents

The `documents/` directory contains project and architectural decisions rather
than executable deployment files:

- `database/db.dbml` is the visual and conceptual database model.
- `automated-pr-review.md` explains the Anthropic pull-request reviewer.
- `demo-data.md` describes demo generation rules and commands.
- `authorization-architecture.md` defines the PostgreSQL membership boundary,
  application authorization interface, and future OpenFGA direction.
- `project-overview.md` is this high-level introduction.

The DBML model and `database/schema.sql` should remain synchronized whenever the
data model changes.

### React frontend

The `web/` directory contains the React application. Vite supplies its development
server and build tooling. The source is organized into components, features, pages,
API services, and shared styles as those areas are introduced.

The frontend consumes the versioned FastAPI endpoints. Its current retro-styled data
browser is a disposable integration aid with list, detail, and pagination views.
Playwright will exercise complete user journeys through a real browser, while
component-level tests can live beside React components when needed.

### Pull-request automation

GitHub Actions discovers workflows beneath `.github/workflows`. The Claude PR
Review workflow asks Anthropic's Claude Code Action to review non-draft pull
requests and post prioritized findings without changing code or approving the PR.
It requires the repository Actions secret `ANTHROPIC_API_KEY`; operational details
are maintained in `documents/automated-pr-review.md`.

## Technology choices

### DBML

DBML provides a readable architecture model for tables, enums, indexes, and
relationships. It supports design discussion without making the diagram itself the
deployment mechanism.

### PostgreSQL

PostgreSQL is the system of record. It enforces UUID relationships, enum values,
uniqueness, date constraints, group hierarchy references, and automatic
`modified_at` timestamps.

The development database is disposable. Removing its Docker volume and starting
again reapplies the schema and seed data from source.

### Seed and demo data

Seed and demo data serve different purposes:

- Seed CSVs are deterministic, reviewable records used when initializing a blank
  development or test database.
- Demo data is fictional data generated with Faker for development, testing, and
  interface demonstrations.

The demo generator can write directly to PostgreSQL or divert identical records to
CSV. Record counts for contacts, family units, and local groups are configurable.
Generated CSVs can be reviewed and curated into stable seed files.

### FastAPI

FastAPI provides the versioned JSON API used by React. Pydantic models define and
validate response contracts, while UUID route parameters receive automatic input
validation. PostgreSQL access currently uses Psycopg.

### React and Vite

React will provide the browser-based CRM interface. Vite supplies the local
development server and frontend build process. The current frontend is a minimal
scaffold ready for feature development.

### Pytest

Pytest verifies the environment, database access, HTTP contracts, and stable API
behavior. API tests are grouped with registered markers and run in an explicit
sequence. The default is:

```text
smoke → contract → regression
```

If a category fails, later categories do not run. More categories can be registered
in `tests/api/pytest.ini` and added to `API_TEST_CATEGORIES`. The category purposes
and run options are documented in [`tests/README.md`](../tests/README.md).

### Playwright

Playwright provides end-to-end browser testing against the running React frontend.
It has its own container because browser binaries and Node dependencies are much
larger than the Python API-test environment.

## Containers

Docker Compose coordinates three application services and two on-demand test
services:

| Service | Responsibility |
| --- | --- |
| `database` | PostgreSQL, schema creation, seed initialization, and persistent local volume |
| `app` | FastAPI development server and API health check |
| `frontend` | React/Vite development server and frontend health check |
| `api-tester` | Demo-data preparation followed by ordered pytest categories |
| `e2e-tester` | Playwright browser tests against the frontend |

Health checks establish startup order. FastAPI waits for PostgreSQL, React waits for
FastAPI, and browser tests wait for React. Test services run only when explicitly
requested.

Common commands from the repository root are:

```shell
docker compose up --build
docker compose run --rm --build api-tester
docker compose run --rm e2e-tester
docker compose down
docker compose down --volumes
```

The last command deletes the disposable database and frontend dependency volumes.
The next startup creates them again from source.

## Environments

The active environment is selected through an environment file. Docker Compose
automatically reads the untracked `.env` file for local development.

Three environments are anticipated:

| Environment | Current purpose | Data behavior |
| --- | --- | --- |
| `development` | Local Docker development | Automatically applies schema and seed data to a fresh volume; demo data is allowed |
| `test` | Future dedicated test execution | Automatically applies schema and seed data; demo data is allowed |
| `production` | Future live deployment | Seed and demo generation are blocked by the current safety rules |

Committed templates document the settings expected by each environment:

- `.env.example`
- `.env.test.example`
- `.env.production.example`

Real environment files and credentials are ignored by Git. Terraform configuration
for an internet-facing test host is available under
`infrastructure/terraform/environments/test`, but no remote resources are currently
provisioned. Production remains configuration scaffolding pending architectural and
operational decisions.
The environment name is included in the Compose project name so containers,
networks, and volumes do not overlap across environments.

# Volunteer CRM

A CRM for managing volunteers, young members, families, organisational groups,
roles, and awards.

The [project overview](documents/project-overview.md) describes the architecture.
The [authorization architecture](documents/authorization-architecture.md) records
the permission model and future OpenFGA boundary.
The [automated PR review guide](documents/automated-pr-review.md) explains the
Anthropic review workflow and required repository secret.

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

Test and production are configuration scaffolds only; no remote deployment is
configured. When those environments are introduced, copy the relevant example to
an ignored environment file and select it explicitly:

```shell
docker compose --env-file .env.test up
docker compose --env-file .env.production up
```

The environment name is included in the Compose project name, keeping its containers,
network, and volumes separate from other environments.

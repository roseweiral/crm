# Volunteer CRM

A CRM for managing volunteers, young members, families, organisational groups,
roles, and awards.

## Local environment

The Docker Compose environment contains four services:

- `database`: the disposable PostgreSQL database
- `app`: the FastAPI application
- `frontend`: the React development server
- `tester`: on-demand environment and application tests

Docker Compose reads the untracked `.env` file by default. This repository's local
file is configured with `APP_ENV=development`.

Start the application:

```shell
docker compose up --build
```

Run the tests:

```shell
docker compose run --rm tester
```

Import the CSV seed data:

```shell
docker compose run --rm app python /database/import_seed.py
```

Stop the services while retaining database data:

```shell
docker compose down
```

Delete the database and frontend dependency volumes for a completely fresh start:

```shell
docker compose down --volumes
```

The schema is automatically applied when PostgreSQL starts with a new database volume.

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

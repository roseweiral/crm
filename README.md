# Volunteer CRM

A CRM for managing volunteers, young members, families, organisational groups,
roles, and awards.

## Local environment

The Docker Compose environment contains four services:

- `database`: the disposable PostgreSQL database
- `app`: the FastAPI application
- `frontend`: the React development server
- `tester`: on-demand environment and application tests

Start the application:

```shell
docker compose up --build
```

Run the tests:

```shell
docker compose run --rm tester
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

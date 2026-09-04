# Web

This directory contains the React and TypeScript web application for the CRM.
Vite provides the local development server inside the `frontend` Docker Compose
service.

The current disposable data browser displays “Hello World” and “Welcome to the New
CRM”, then provides paginated list and detail views for the main read-only API
resources. Its intentionally retro visual treatment uses only local CSS: monospace
type, terminal colours, hard borders, and offset shadows.

This interface exists to exercise the API while the product design is still being
formed. It is expected to be replaced rather than treated as the final CRM design.

Build and type-check the frontend through its Docker image:

```shell
docker compose build frontend
```

Run the browser tests from the repository root:

```shell
docker compose run --rm --build e2e-tester
```

The run persists an HTML report. Start its viewer with
`docker compose --profile test up -d e2e-report`, then open
`http://localhost:9323`.

See [`app/routers/README.md`](../app/routers/README.md) for the HTTP API that this
frontend will consume.

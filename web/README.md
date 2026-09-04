# Web

This directory contains the React and TypeScript web application for the CRM.
Vite provides the local development server inside the `frontend` Docker Compose
service.

The initial landing page displays “Hello World” and “Welcome to the New CRM”. Its
browser contract is covered by the TypeScript Playwright test in `tests/e2e`.

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

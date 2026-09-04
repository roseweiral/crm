# Tests

This directory contains tests that exercise behavior across the API, web application,
and database.

- `api/` contains pytest endpoint and PostgreSQL integration tests.
- `e2e/` contains Playwright browser tests for the React application.
- `fixtures/` contains reusable test inputs that do not belong in seed or demo data.

The API tester uses the same disposable local database as the application.

Endpoint work follows test-driven development: contract tests are added and observed
failing before the corresponding FastAPI implementation is written.

API categories run sequentially in the order defined by `API_TEST_CATEGORIES`.
The default is `smoke,contract`. A failing category stops the run, so endpoint tests
are skipped when the environment smoke tests fail. Register new markers in
`api/pytest.ini` before adding them to the configured sequence.

## Playwright report

Every end-to-end test run writes a persistent HTML report to
`tests/e2e/playwright-report`. The directory is ignored by Git, so reports remain
available locally without becoming source files.

Generate or refresh the report:

```shell
docker compose run --rm --build e2e-tester
```

Serve the latest report:

```shell
docker compose --profile test up -d e2e-report
```

Open `http://localhost:9323`. Stop the viewer with:

```shell
docker compose --profile test stop e2e-report
```

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
The default is `smoke,contract,regression`. A failing category stops the run, so
later and more expensive tests are skipped when an earlier category fails:

1. `smoke` confirms that the API and database are reachable.
2. `contract` confirms the shape and status codes of each endpoint.
3. `regression` confirms pagination, filtering, relationships, and stable demo-data
   expectations.

Categories can be selected or reordered for one run, for example:

```shell
API_TEST_CATEGORIES=smoke,regression docker compose run --rm --build api-tester
```

Extra pytest options can be passed through `PYTEST_ARGS`. Register new markers in
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

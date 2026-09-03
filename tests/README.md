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

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

## Pytest TDD workflow

Use a separate Compose project and the example test configuration so test runs do
not replace your development database. The `api-tester` service **replaces its
configured database with demo data before each run**. Do not point it at a database
whose contents you need to retain.

Run the complete API suite:

```shell
docker compose --env-file .env.test.example -p crm-pytest --profile test run --rm --build api-tester
```

Run one test while developing:

```shell
PYTEST_ARGS='-q -k test_invitation_cannot_reactivate_disabled_account' docker compose --env-file .env.test.example -p crm-pytest --profile test run --rm --build api-tester
```

Run one category:

```shell
API_TEST_CATEGORIES=contract docker compose --env-file .env.test.example -p crm-pytest --profile test run --rm --build api-tester
```

Compose forwards `PYTEST_ARGS` to the runner. Categories with no matching tests are
skipped; if nothing matches across all categories, the runner exits with code 5.
Test failures and collection errors still stop subsequent categories. Use `-k` for
focused selection; let `API_TEST_CATEGORIES` control markers rather than overriding
`-m` in `PYTEST_ARGS`.

1. Add a behavior test and run it alone. Confirm it fails for the intended reason,
   rather than an unavailable service or broken fixture.
2. Make the smallest implementation change that makes it pass.
3. Refactor, rerun the focused test, then run the complete suite.

The tester installs both API and pytest dependencies. It runs HTTP tests against
the Compose API and transaction tests through FastAPI's test client against the
same PostgreSQL database. The latter replace only the OIDC exchange; real fake-OIDC
HTTP tests still exercise the authorization-code flow. The fake provider reads test
contacts from PostgreSQL so disposable identities can participate in those tests.

Use `records`, `person`, and `session_token` fixtures for test-owned data. Rows are
committed so other request connections can see them, and teardown removes them
even when assertions fail. Create explicit relationship graphs instead of modifying
demo users. Demo counts are asserted separately from isolated behavior scenarios.
Run this shared-database suite serially; parallel workers require separate databases.

To check repeatability without resetting the database, after the initial run:

```shell
docker compose --env-file .env.test.example -p crm-pytest --profile test run --rm api-tester python tests/api/run_tests.py
```

Remove the disposable environment when finished:

```shell
docker compose --env-file .env.test.example -p crm-pytest --profile test down -v
```

"""Run pytest categories sequentially, stopping when a category fails."""

from __future__ import annotations

import os
import hashlib
import secrets
import shlex
import subprocess

import psycopg


DEFAULT_CATEGORIES = "smoke,contract,regression"


def configured_categories() -> list[str]:
    raw_categories = os.environ.get("TEST_CATEGORIES", DEFAULT_CATEGORIES)
    categories = [category.strip() for category in raw_categories.split(",")]
    categories = [category for category in categories if category]

    if not categories:
        raise RuntimeError("TEST_CATEGORIES must contain at least one pytest marker")

    return categories


def main() -> int:
    raw_session = secrets.token_urlsafe(48)
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        account_id = connection.execute(
            """
            SELECT uara.user_account_id
            FROM user_access_role_assignments uara
            JOIN access_roles ar ON ar.id = uara.access_role_id
            WHERE ar.is_global
            ORDER BY uara.id
            LIMIT 1
            """
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO user_sessions (user_account_id, token_hash)
            VALUES (%s, %s)
            """,
            (account_id, hashlib.sha256(raw_session.encode()).hexdigest()),
        )
    os.environ["AUTH_TEST_SESSION_TOKEN"] = raw_session

    try:
        return run_categories(
            configured_categories(), shlex.split(os.environ.get("PYTEST_ARGS", ""))
        )
    finally:
        with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
            connection.execute(
                "DELETE FROM user_sessions WHERE token_hash = %s",
                (hashlib.sha256(raw_session.encode()).hexdigest(),),
            )


def run_categories(categories: list[str], extra_arguments: list[str]) -> int:
    ran_tests = False
    for category in categories:
        print(f"\n=== RUNNING {category.upper()} TESTS ===", flush=True)
        result = subprocess.run(
            [
                "pytest",
                "-c",
                "tests/api/pytest.ini",
                "-m",
                category,
                "tests/api",
                *extra_arguments,
            ],
            check=False,
        )
        if result.returncode == 5:
            print(f"No tests selected in {category}", flush=True)
            continue
        if result.returncode != 0:
            return result.returncode
        ran_tests = True
    if not ran_tests:
        print(
            "No tests matched the selected categories and pytest arguments", flush=True
        )
        return 5
    print("All selected tests passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

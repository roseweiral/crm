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

    extra_arguments = shlex.split(os.environ.get("PYTEST_ARGS", ""))

    for category in configured_categories():
        print(f"\n=== RUNNING {category.upper()} TESTS ===", flush=True)
        command = [
            "pytest",
            "-c",
            "tests/api/pytest.ini",
            "-m",
            category,
            "tests/api",
            *extra_arguments,
        ]
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            print(
                f"\n{category.upper()} TESTS FAILED; LATER CATEGORIES SKIPPED",
                flush=True,
            )
            return result.returncode

        print(f"{category.upper()} TESTS PASSED", flush=True)

    print("\nALL CONFIGURED TEST CATEGORIES PASSED", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

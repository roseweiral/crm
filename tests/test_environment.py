"""Smoke tests for the local Docker environment."""

import os

import httpx
import psycopg


def test_database_is_available() -> None:
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        assert connection.execute("SELECT 1").fetchone() == (1,)


def test_api_is_available() -> None:
    response = httpx.get(f"{os.environ['API_URL']}/health", timeout=5)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

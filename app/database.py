"""PostgreSQL connection dependencies for FastAPI routes."""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row


def get_database_url() -> str:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set")
    return database_url


def get_connection() -> Generator[Connection[Any], None, None]:
    """Provide one database connection for the lifetime of a request."""
    with psycopg.connect(get_database_url(), row_factory=dict_row) as connection:
        yield connection

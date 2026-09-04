"""Shared database and HTTP assertions for API contract tests."""

from __future__ import annotations

import os
from datetime import date
from enum import Enum
from typing import Any
from uuid import UUID

import httpx
import psycopg
from psycopg.rows import dict_row


API_URL = os.environ["API_URL"]
DATABASE_URL = os.environ["DATABASE_URL"]


def database_rows(query: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        return list(connection.execute(query, parameters).fetchall())


def serialise(value: Any) -> Any:
    if isinstance(value, (UUID, date, Enum)):
        return str(value)
    if isinstance(value, dict):
        return {key: serialise(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialise(item) for item in value]
    return value


def assert_first_page(
    path: str,
    table: str,
    columns: tuple[str, ...],
    order_by: str,
) -> list[dict[str, Any]]:
    selected_columns = ", ".join(columns)
    expected_rows = database_rows(
        f"""
        SELECT {selected_columns}
        FROM {table}
        ORDER BY {order_by}
        LIMIT 25
        """
    )
    total = database_rows(f"SELECT count(*) AS total FROM {table}")[0]["total"]

    response = httpx.get(f"{API_URL}{path}", timeout=5)

    assert response.status_code == 200
    assert response.json() == {
        "items": serialise(expected_rows),
        "page": 1,
        "page_size": 25,
        "total": total,
    }
    return expected_rows

"""Import deterministic CSV seed data into a blank PostgreSQL database."""

from __future__ import annotations

import csv
import os
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from psycopg import Connection, sql


SEED_DIRECTORY = Path(__file__).with_name("seed")

TABLE_COLUMNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "contacts",
        (
            "id", "first_name", "last_name", "email", "status", "can_login",
            "date_of_birth", "preferred_name", "phonetic_name", "pronouns", "gender",
        ),
    ),
    ("user_accounts", ("id", "contact_id", "status")),
    (
        "user_identities",
        (
            "id", "user_account_id", "provider", "issuer", "subject", "email",
            "email_verified", "last_signed_in_at",
        ),
    ),
    (
        "invitations",
        (
            "id", "user_account_id", "invited_by_user_account_id", "email",
            "token_hash", "expires_at", "accepted_at", "revoked_at",
        ),
    ),
    (
        "user_sessions",
        (
            "id", "user_account_id", "token_hash", "expires_at", "last_seen_at",
            "revoked_at",
        ),
    ),
    ("role_types", ("id", "name", "description")),
    ("group_types", ("id", "name", "description")),
    ("family_units", ("id",)),
    ("award_types", ("id", "name", "description")),
    ("groups", ("id", "group_type_id", "name", "description", "parent_id")),
    (
        "contact_roles_groups",
        ("id", "contact_id", "role_type_id", "group_id", "start_date", "end_date"),
    ),
    (
        "contact_family_units",
        ("id", "contact_id", "family_unit_id", "relationship"),
    ),
    (
        "contact_family_main_contacts",
        ("id", "family_unit_id", "contact_id", "start_date", "end_date"),
    ),
    (
        "contact_phone_numbers",
        (
            "id", "contact_id", "phone_type", "number", "is_primary", "start_date",
            "end_date",
        ),
    ),
    (
        "contact_addresses",
        (
            "id", "contact_id", "address_type", "line1", "line2", "city", "region",
            "postcode", "country", "start_date", "end_date",
        ),
    ),
    (
        "contact_emergency_contacts",
        ("id", "contact_id", "emergency_contact_id", "priority", "relationship"),
    ),
    (
        "contact_awards",
        (
            "id",
            "contact_id",
            "award_type_id",
            "status",
            "nomination_date",
            "presented_date",
            "notes",
        ),
    ),
    ("permissions", ("id", "name", "description")),
    ("access_roles", ("id", "name", "description", "is_global")),
    (
        "access_role_permissions",
        ("access_role_id", "permission_id"),
    ),
    (
        "user_access_role_assignments",
        (
            "id", "user_account_id", "access_role_id", "group_id", "start_date",
            "end_date",
        ),
    ),
    (
        "audit_events",
        (
            "id", "user_account_id", "event_type", "outcome", "provider",
            "subject", "ip_address", "user_agent", "details",
        ),
    ),
)


def parse_boolean(value: str) -> bool:
    normalised_value = value.strip().lower()
    if normalised_value in {"true", "t", "yes", "y", "1"}:
        return True
    if normalised_value in {"false", "f", "no", "n", "0"}:
        return False
    raise ValueError(f"invalid boolean value: {value!r}")


def converter_for(table: str, column: str) -> Callable[[str], Any]:
    if column == "id" or column.endswith("_id"):
        return UUID
    if column.endswith("_date"):
        return date.fromisoformat
    if column.endswith("_at"):
        return datetime.fromisoformat
    if column in {"can_login", "email_verified", "is_global", "is_primary"}:
        return parse_boolean
    if column == "priority":
        return int
    return str


def parse_value(table: str, column: str, value: str | None) -> Any:
    if value is None or value.strip() == "":
        return None
    return converter_for(table, column)(value.strip())


def read_rows(
    table: str, csv_path: Path, expected_columns: tuple[str, ...]
) -> list[tuple[Any, ...]]:
    with csv_path.open(encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        actual_columns = tuple(reader.fieldnames or ())

        if actual_columns != expected_columns:
            raise ValueError(
                f"{csv_path.name} has headers {actual_columns}; expected {expected_columns}"
            )

        return [
            tuple(parse_value(table, column, row[column]) for column in expected_columns)
            for row in reader
        ]


def insert_rows(
    connection: Connection[Any],
    table: str,
    columns: tuple[str, ...],
    rows: list[tuple[Any, ...]],
) -> int:
    if not rows:
        return 0

    statement = sql.SQL("INSERT INTO {table} ({columns}) VALUES ({values})").format(
        table=sql.Identifier(table),
        columns=sql.SQL(", ").join(map(sql.Identifier, columns)),
        values=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )

    with connection.cursor() as cursor:
        cursor.executemany(statement, rows)

    return len(rows)


def import_seed_data(
    connection: Connection[Any], seed_directory: Path = SEED_DIRECTORY
) -> int:
    """Import every seed CSV in dependency order within one transaction."""
    total_records = 0

    for table, columns in TABLE_COLUMNS:
        csv_path = seed_directory / f"{table}.csv"
        if not csv_path.is_file():
            raise FileNotFoundError(f"Missing seed file: {csv_path}")

        rows = read_rows(table, csv_path, columns)
        records_added = insert_rows(connection, table, columns, rows)
        total_records += records_added
        print(f"{table}: {records_added} RECORDS ADDED")

    return total_records


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set")

    with psycopg.connect(database_url) as connection:
        total_records = import_seed_data(connection)

    print(f"TOTAL: {total_records} RECORDS ADDED")
    return total_records


if __name__ == "__main__":
    main()

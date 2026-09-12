"""Output adapters for generated demo records."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import psycopg
from psycopg import Connection, sql

from demo.context import DemoContext
from import_seed import TABLE_COLUMNS, insert_rows


TABLES = tuple(table for table, _ in TABLE_COLUMNS)
INITIALIZATION_EVENT = "demo_data.initialized"
SEED_OWNED_AUTHORIZATION_TABLES = {
    "permissions",
    "access_roles",
    "access_role_permissions",
    "user_access_role_assignments",
}


def write_csv_files(context: DemoContext, output_directory: Path) -> int:
    output_directory.mkdir(parents=True, exist_ok=True)
    total_records = 0

    for table, columns in TABLE_COLUMNS:
        rows = context.rows[table]
        output_path = output_directory / f"{table}.csv"

        with output_path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=columns, extrasaction="raise")
            writer.writeheader()
            writer.writerows(rows)

        total_records += len(rows)
        print(f"{table}: {len(rows)} RECORDS WRITTEN TO {output_path}")

    return total_records


def ensure_database_is_empty(connection: Connection[Any]) -> None:
    populated_tables: list[str] = []

    with connection.cursor() as cursor:
        for table in TABLES:
            cursor.execute(
                sql.SQL("SELECT EXISTS (SELECT 1 FROM {} LIMIT 1)").format(
                    sql.Identifier(table)
                )
            )
            if cursor.fetchone()[0]:
                populated_tables.append(table)

    if populated_tables:
        raise RuntimeError(
            "Database is not empty "
            f"({', '.join(populated_tables)}). Use --replace to clear demo tables."
        )


def clear_database(connection: Connection[Any]) -> None:
    table_names = sql.SQL(", ").join(map(sql.Identifier, reversed(TABLES)))
    with connection.cursor() as cursor:
        cursor.execute(
            sql.SQL("TRUNCATE TABLE {} CASCADE").format(table_names)
        )


def insert_rows_ignoring_conflicts(
    connection: Connection[Any],
    table: str,
    columns: tuple[str, ...],
    rows: list[tuple[Any, ...]],
) -> int:
    if not rows:
        return 0

    statement = sql.SQL(
        "INSERT INTO {table} ({columns}) VALUES ({values}) ON CONFLICT DO NOTHING"
    ).format(
        table=sql.Identifier(table),
        columns=sql.SQL(", ").join(map(sql.Identifier, columns)),
        values=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )
    with connection.cursor() as cursor:
        cursor.executemany(statement, rows)
        return cursor.rowcount


def append_demo_rows(
    connection: Connection[Any], context: DemoContext
) -> int:
    existing_contact_ids = {
        row[0] for row in connection.execute("SELECT id FROM contacts").fetchall()
    }
    generated_contact_ids = {row["id"] for row in context.rows["contacts"]}
    new_contact_ids = generated_contact_ids - existing_contact_ids
    new_account_ids = {
        row["id"]
        for row in context.rows["user_accounts"]
        if row["contact_id"] in new_contact_ids
    }
    existing_groups = {
        row[0]: row[1]
        for row in connection.execute("SELECT name, id FROM groups").fetchall()
    }
    group_id_map = {
        row["id"]: existing_groups[row["name"]]
        for row in context.rows["groups"]
        if row["name"] in existing_groups
    }

    def remap_group_id(value: Any) -> Any:
        return group_id_map.get(value, value)

    total_records = 0
    for table, columns in TABLE_COLUMNS:
        if table in SEED_OWNED_AUTHORIZATION_TABLES:
            print(f"{table}: 0 RECORDS ADDED (seed configuration retained)")
            continue

        records = [row.copy() for row in context.rows[table]]
        if table == "user_accounts":
            records = [row for row in records if row["id"] in new_account_ids]
        elif table in {"user_identities", "invitations", "user_sessions"}:
            records = [
                row for row in records if row["user_account_id"] in new_account_ids
            ]
        elif table == "groups":
            records = [
                row for row in records if row["id"] not in group_id_map
            ]
            for row in records:
                row["parent_id"] = remap_group_id(row["parent_id"])
        elif table == "contact_roles_groups":
            for row in records:
                row["group_id"] = remap_group_id(row["group_id"])

        row_values = [
            tuple(row[column] for column in columns) for row in records
        ]
        records_added = insert_rows_ignoring_conflicts(
            connection, table, columns, row_values
        )
        total_records += records_added
        print(f"{table}: {records_added} RECORDS ADDED")

    generated_identities = context.rows["user_identities"]
    if generated_identities:
        connection.execute(
            "UPDATE user_identities SET issuer = %s WHERE provider = 'google'",
            (generated_identities[0]["issuer"],),
        )

    return total_records


def write_database(
    context: DemoContext,
    database_url: str,
    replace_existing: bool,
    *,
    initialize_once: bool = False,
) -> int:
    total_records = 0

    with psycopg.connect(database_url) as connection:
        if initialize_once:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                (INITIALIZATION_EVENT,),
            )
            initialized = connection.execute(
                "SELECT EXISTS (SELECT 1 FROM audit_events WHERE event_type = %s)",
                (INITIALIZATION_EVENT,),
            ).fetchone()[0]
            if initialized:
                print("Demo data is already initialized; leaving the database unchanged")
                return 0

            total_records = append_demo_rows(connection, context)
            connection.execute(
                """
                INSERT INTO audit_events (event_type, outcome, details)
                VALUES (%s, 'success', %s)
                """,
                (
                    INITIALIZATION_EVENT,
                    psycopg.types.json.Jsonb({"mode": "append-once"}),
                ),
            )
            return total_records

        if replace_existing:
            clear_database(connection)
        else:
            ensure_database_is_empty(connection)

        for table, columns in TABLE_COLUMNS:
            row_values = [
                tuple(row[column] for column in columns) for row in context.rows[table]
            ]
            records_added = insert_rows(connection, table, columns, row_values)
            total_records += records_added
            print(f"{table}: {records_added} RECORDS ADDED")

    return total_records

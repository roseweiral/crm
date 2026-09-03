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


def write_database(
    context: DemoContext, database_url: str, replace_existing: bool
) -> int:
    total_records = 0

    with psycopg.connect(database_url) as connection:
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

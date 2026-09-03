"""Generate coherent demo records and write them to PostgreSQL or CSV."""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path

from demo import (
    award_types,
    contact_awards,
    contact_family_units,
    contact_roles_groups,
    contacts,
    family_units,
    group_types,
    groups,
    role_types,
)
from demo.context import DemoConfig, DemoContext
from demo.output import write_csv_files, write_database


DEMO_DATA_MODULES: tuple[Callable[[DemoContext], int], ...] = (
    role_types.populate,
    group_types.populate,
    award_types.populate,
    contacts.populate,
    family_units.populate,
    groups.populate,
    contact_roles_groups.populate,
    contact_family_units.populate,
    contact_awards.populate,
)

DEMO_DATA_ENVIRONMENTS = {"development", "test"}
DEFAULT_CSV_DIRECTORY = Path(__file__).with_name("generated")


def positive_integer(value: str) -> int:
    parsed_value = int(value)
    if parsed_value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed_value


def non_negative_integer(value: str) -> int:
    parsed_value = int(value)
    if parsed_value < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed_value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", choices=("database", "csv"), default="database")
    parser.add_argument("--contacts", type=positive_integer, default=60)
    parser.add_argument("--families", type=non_negative_integer, default=15)
    parser.add_argument(
        "--groups",
        type=positive_integer,
        default=6,
        help="number of local leaf groups to create",
    )
    parser.add_argument("--random-seed", type=int, default=20260903)
    parser.add_argument("--as-of-date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--csv-directory", type=Path, default=DEFAULT_CSV_DIRECTORY)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="clear existing database records before inserting demo data",
    )
    return parser


def validate_counts(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    minimum_contacts = max(3, args.families * 2)
    if args.contacts < minimum_contacts:
        parser.error(
            f"--contacts must be at least {minimum_contacts} for {args.families} "
            "families and the required leadership roles"
        )


def generate_records(config: DemoConfig) -> DemoContext:
    context = DemoContext(config=config)
    for populate in DEMO_DATA_MODULES:
        populate(context)
    return context


def main(arguments: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(arguments)
    validate_counts(parser, args)

    context = generate_records(
        DemoConfig(
            contact_count=args.contacts,
            family_count=args.families,
            unit_count=args.groups,
            random_seed=args.random_seed,
            as_of_date=args.as_of_date,
        )
    )

    if args.output == "csv":
        total_records = write_csv_files(context, args.csv_directory)
    else:
        app_environment = os.environ.get("APP_ENV")
        if app_environment not in DEMO_DATA_ENVIRONMENTS:
            parser.error(
                "database output is allowed only when APP_ENV is development or test"
            )

        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            parser.error("DATABASE_URL must be set for database output")

        total_records = write_database(context, database_url, args.replace)

    print(f"TOTAL: {total_records} RECORDS GENERATED")
    return total_records


if __name__ == "__main__":
    main()

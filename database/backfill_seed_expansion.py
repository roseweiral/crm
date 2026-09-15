"""One-off backfill: add the contact-data-expansion fields/tables to the
already-curated CSVs under database/seed/.

database/seed/*.csv predate the personal-details columns and the
contact_family_main_contacts/contact_phone_numbers/contact_addresses/
contact_emergency_contacts tables added this session, and at least one row
(the first contact) has been hand-edited since it was originally
generated (see database/seed/README.md - IDs must remain stable once other
files refer to them). Regenerating the seed CSVs from scratch with
database/demo_data.py would silently discard that curation, so this script
instead reuses the real generator modules (database/demo/contacts.py's
_personal_details, and the contact_family_main_contacts/
contact_phone_numbers/contact_addresses/contact_emergency_contacts
modules unchanged) against a DemoContext built from the *existing* CSV
content - every existing column, row, and ID is left untouched; only the
five new contacts.csv columns and four new CSV files are added.

Run once, from the repository root:

    docker compose run --rm app python /database/backfill_seed_expansion.py

Safe to delete after running - it is not part of the regular demo-data
generation flow (database/demo_data.py) and is not idempotent against its
own output (rerunning it would add a second, different set of generated
rows for the four new tables).
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from uuid import UUID

from demo import (
    contact_addresses,
    contact_emergency_contacts,
    contact_family_main_contacts,
    contact_phone_numbers,
)
from demo.context import DemoConfig, DemoContext
from demo.contacts import _personal_details

SEED_DIRECTORY = Path(__file__).with_name("seed")
RANDOM_SEED = 20260903
AS_OF_DATE = date(2026, 1, 1)

NEW_CONTACT_COLUMNS = ("date_of_birth", "preferred_name", "phonetic_name", "pronouns", "gender")


def read_csv(name: str) -> list[dict[str, str]]:
    with (SEED_DIRECTORY / name).open(encoding="utf-8-sig", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def write_csv(name: str, fieldnames: tuple[str, ...], rows: list[dict[str, object]]) -> None:
    output_path = SEED_DIRECTORY / name
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: ("" if value is None else value) for key, value in row.items()})
    print(f"{name}: {len(rows)} ROWS WRITTEN")


def build_context() -> tuple[DemoContext, list[dict[str, str]]]:
    contact_rows = read_csv("contacts.csv")
    family_rows = read_csv("family_units.csv")
    relationship_rows = read_csv("contact_family_units.csv")

    parent_by_family: dict[str, str] = {}
    child_by_family: dict[str, str] = {}
    for row in relationship_rows:
        if row["relationship"] == "parent":
            parent_by_family[row["family_unit_id"]] = row["contact_id"]
        elif row["relationship"] == "child":
            child_by_family[row["family_unit_id"]] = row["contact_id"]

    family_unit_ids = [UUID(row["id"]) for row in family_rows]
    ordered_child_ids = {child_by_family[row["id"]] for row in family_rows}

    context = DemoContext(
        config=DemoConfig(
            contact_count=len(contact_rows),
            family_count=len(family_rows),
            unit_count=1,  # unused by the modules this script calls
            random_seed=RANDOM_SEED,
            as_of_date=AS_OF_DATE,
        )
    )
    context.family_unit_ids.extend(family_unit_ids)
    # Index-aligned with family_unit_ids, exactly as contact_family_main_contacts.py
    # and contact_emergency_contacts.py expect (family i's parent/child at index i).
    context.adult_contact_ids.extend(UUID(parent_by_family[str(fid)]) for fid in family_unit_ids)
    context.child_contact_ids.extend(UUID(child_by_family[str(fid)]) for fid in family_unit_ids)
    # Remaining adults: every other contact not already a family parent or child.
    context.adult_contact_ids.extend(
        UUID(row["id"])
        for row in contact_rows
        if row["id"] not in parent_by_family.values() and row["id"] not in ordered_child_ids
    )

    return context, contact_rows


def backfill_contacts(context: DemoContext, contact_rows: list[dict[str, str]]) -> None:
    child_ids = {str(contact_id) for contact_id in context.child_contact_ids}

    for row in contact_rows:
        is_adult = row["id"] not in child_ids
        details = _personal_details(context, row["first_name"], is_adult)
        row.update({key: (value if value is not None else "") for key, value in details.items()})

    write_csv(
        "contacts.csv",
        ("id", "first_name", "last_name", "email", "status", "can_login", *NEW_CONTACT_COLUMNS),
        contact_rows,
    )


def main() -> None:
    context, contact_rows = build_context()

    backfill_contacts(context, contact_rows)

    contact_family_main_contacts.populate(context)
    write_csv(
        "contact_family_main_contacts.csv",
        ("id", "family_unit_id", "contact_id", "start_date", "end_date"),
        context.rows["contact_family_main_contacts"],
    )

    contact_phone_numbers.populate(context)
    write_csv(
        "contact_phone_numbers.csv",
        ("id", "contact_id", "phone_type", "number", "is_primary", "start_date", "end_date"),
        context.rows["contact_phone_numbers"],
    )

    contact_addresses.populate(context)
    write_csv(
        "contact_addresses.csv",
        (
            "id", "contact_id", "address_type", "line1", "line2", "city", "region",
            "postcode", "country", "start_date", "end_date",
        ),
        context.rows["contact_addresses"],
    )

    contact_emergency_contacts.populate(context)
    write_csv(
        "contact_emergency_contacts.csv",
        ("id", "contact_id", "emergency_contact_id", "priority", "relationship"),
        context.rows["contact_emergency_contacts"],
    )


if __name__ == "__main__":
    main()

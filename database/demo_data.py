"""Generate demo data in database dependency order."""

from collections.abc import Callable

from demo import (
    award_types,
    contact_awards,
    contact_families,
    contact_roles_groups,
    contacts,
    families,
    group_types,
    groups,
    role_types,
)


DEMO_DATA_MODULES: tuple[Callable[[], int], ...] = (
    contacts.populate,
    role_types.populate,
    group_types.populate,
    families.populate,
    award_types.populate,
    groups.populate,
    contact_roles_groups.populate,
    contact_families.populate,
    contact_awards.populate,
)


def main() -> int:
    """Run every demo-data module and report the combined record count."""
    total_records = sum(populate() for populate in DEMO_DATA_MODULES)
    print(f"TOTAL: {total_records} RECORDS ADDED")
    return total_records


if __name__ == "__main__":
    main()

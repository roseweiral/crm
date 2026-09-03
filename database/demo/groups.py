"""Demo data for groups."""

from math import ceil
from uuid import UUID

from demo.context import DemoContext


PREFERRED_TOWNS = (
    "Croydon",
    "Bromley",
    "Sutton",
    "Lewisham",
    "Greenwich",
    "Kingston",
    "Richmond",
    "Wimbledon",
)


def populate(context: DemoContext) -> int:
    hq_id = context.stable_uuid("group", "hq")
    county_id = context.stable_uuid("group", "greater-london")
    city_id = context.stable_uuid("group", "london")
    rows: list[dict[str, object]] = [
        {
            "id": hq_id,
            "group_type_id": context.group_type_ids["hq"],
            "name": "HQ",
            "description": "Organisation headquarters",
            "parent_id": None,
        },
        {
            "id": county_id,
            "group_type_id": context.group_type_ids["county"],
            "name": "Greater London",
            "description": "Greater London county",
            "parent_id": hq_id,
        },
        {
            "id": city_id,
            "group_type_id": context.group_type_ids["city"],
            "name": "London",
            "description": "London city area",
            "parent_id": county_id,
        },
    ]
    context.management_group_ids.extend((hq_id, county_id, city_id))

    town_count = ceil(context.config.unit_count / 3)
    town_ids: list[UUID] = []

    for town_index in range(town_count):
        if town_index < len(PREFERRED_TOWNS):
            town_name = PREFERRED_TOWNS[town_index]
        else:
            town_name = f"{context.fake.unique.city()} {town_index + 1}"

        town_id = context.stable_uuid("group", f"town-{town_index + 1}")
        town_ids.append(town_id)
        context.management_group_ids.append(town_id)
        rows.append(
            {
                "id": town_id,
                "group_type_id": context.group_type_ids["town"],
                "name": town_name,
                "description": f"{town_name} town area",
                "parent_id": city_id,
            }
        )

    units_per_town: dict[UUID, int] = {town_id: 0 for town_id in town_ids}
    towns_by_id = {row["id"]: row["name"] for row in rows if row["id"] in town_ids}

    for unit_index in range(context.config.unit_count):
        town_id = town_ids[unit_index % len(town_ids)]
        units_per_town[town_id] += 1
        group_number = units_per_town[town_id]
        town_name = towns_by_id[town_id]
        unit_id = context.stable_uuid("group", f"unit-{unit_index + 1}")

        context.unit_group_ids.append(unit_id)
        rows.append(
            {
                "id": unit_id,
                "group_type_id": context.group_type_ids["group"],
                "name": f"{town_name} Group {group_number}",
                "description": f"Local group serving {town_name}",
                "parent_id": town_id,
            }
        )

    return context.set_rows("groups", rows)

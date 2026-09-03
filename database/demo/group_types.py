"""Demo data for group types."""

from demo.context import DemoContext


def populate(context: DemoContext) -> int:
    context.group_type_ids = {
        name: context.stable_uuid("group-type", name)
        for name in ("hq", "county", "city", "town", "group")
    }
    return context.set_rows(
        "group_types",
        [
            {"id": context.group_type_ids["hq"], "name": "HQ", "description": "Organisation headquarters"},
            {"id": context.group_type_ids["county"], "name": "County", "description": "County-level area"},
            {"id": context.group_type_ids["city"], "name": "City", "description": "City-level area"},
            {"id": context.group_type_ids["town"], "name": "Town", "description": "Town-level area"},
            {"id": context.group_type_ids["group"], "name": "Group", "description": "Local member unit"},
        ],
    )

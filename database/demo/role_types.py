"""Demo data for role types."""

from demo.context import DemoContext


def populate(context: DemoContext) -> int:
    context.role_type_ids = {
        "group_leader": context.stable_uuid("role-type", "group-leader"),
        "group_helper": context.stable_uuid("role-type", "group-helper"),
        "area_manager": context.stable_uuid("role-type", "area-manager"),
    }
    return context.set_rows(
        "role_types",
        [
            {"id": context.role_type_ids["group_leader"], "name": "Group Leader", "description": "Leads a local group"},
            {"id": context.role_type_ids["group_helper"], "name": "Group Helper", "description": "Supports a local group"},
            {"id": context.role_type_ids["area_manager"], "name": "Area Manager", "description": "Leads an organisational area"},
        ],
    )

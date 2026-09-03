"""Demo data for contact, role, and group assignments."""

from itertools import cycle

from demo.context import DemoContext


def populate(context: DemoContext) -> int:
    rows = []
    adults = cycle(context.adult_contact_ids)
    start_date = context.config.as_of_date.replace(month=1, day=1)
    assignment_number = 1

    for group_id in context.management_group_ids:
        rows.append(
            {
                "id": context.stable_uuid("contact-role-group", assignment_number),
                "contact_id": next(adults),
                "role_type_id": context.role_type_ids["area_manager"],
                "group_id": group_id,
                "start_date": start_date,
                "end_date": None,
            }
        )
        assignment_number += 1

    for group_id in context.unit_group_ids:
        for role_type_id in (
            context.role_type_ids["group_leader"],
            context.role_type_ids["group_helper"],
            context.role_type_ids["group_helper"],
        ):
            rows.append(
                {
                    "id": context.stable_uuid(
                        "contact-role-group", assignment_number
                    ),
                    "contact_id": next(adults),
                    "role_type_id": role_type_id,
                    "group_id": group_id,
                    "start_date": start_date,
                    "end_date": None,
                }
            )
            assignment_number += 1

    return context.set_rows("contact_roles_groups", rows)

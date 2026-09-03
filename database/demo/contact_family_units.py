"""Demo data for contact and family-unit relationships."""

from demo.context import DemoContext


def populate(context: DemoContext) -> int:
    rows = []
    relationship_number = 1

    for index, family_unit_id in enumerate(context.family_unit_ids):
        rows.append(
            {
                "id": context.stable_uuid(
                    "contact-family-unit", relationship_number
                ),
                "contact_id": context.adult_contact_ids[index],
                "family_unit_id": family_unit_id,
                "relationship": "parent",
            }
        )
        relationship_number += 1
        rows.append(
            {
                "id": context.stable_uuid(
                    "contact-family-unit", relationship_number
                ),
                "contact_id": context.child_contact_ids[index],
                "family_unit_id": family_unit_id,
                "relationship": "child",
            }
        )
        relationship_number += 1

    return context.set_rows("contact_family_units", rows)

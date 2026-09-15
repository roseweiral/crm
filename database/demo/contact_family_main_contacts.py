"""Demo data for family Main Contact tracking.

Each family unit's one parent (contact_family_units.py pairs
adult_contact_ids[i] with the family at the same index) is set as that
family's current Main Contact.
"""

from demo.context import DemoContext


def populate(context: DemoContext) -> int:
    rows = []
    start_date = context.config.as_of_date.replace(month=1, day=1)

    for index, family_unit_id in enumerate(context.family_unit_ids):
        rows.append(
            {
                "id": context.stable_uuid("contact-family-main-contact", index + 1),
                "family_unit_id": family_unit_id,
                "contact_id": context.adult_contact_ids[index],
                "start_date": start_date,
                "end_date": None,
            }
        )

    return context.set_rows("contact_family_main_contacts", rows)

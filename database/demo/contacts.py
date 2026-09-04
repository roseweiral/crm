"""Demo data for contacts."""

from demo.context import DemoContext


def populate(context: DemoContext) -> int:
    rows: list[dict[str, object]] = []
    adult_count = context.config.contact_count - context.config.family_count

    for contact_number in range(1, context.config.contact_count + 1):
        contact_id = context.stable_uuid("contact", contact_number)
        first_name = context.fake.first_name()
        last_name = context.fake.last_name()
        is_adult = contact_number <= adult_count
        email = f"{first_name}.{last_name}.{contact_number}@crm-seed-data.abc".lower()

        rows.append(
            {
                "id": contact_id,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "status": "active",
                "can_login": True,
            }
        )

        target = context.adult_contact_ids if is_adult else context.child_contact_ids
        target.append(contact_id)

    return context.set_rows("contacts", rows)

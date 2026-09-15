"""Demo data for contact phone numbers.

Adults only - children don't get independent phone numbers in this demo
dataset, matching how contact_addresses.py and real-world CRM data for
minors typically works. Most adults get one primary mobile number; a
minority also get a second, non-primary number.
"""

from demo.context import DemoContext


def populate(context: DemoContext) -> int:
    rows: list[dict[str, object]] = []
    start_date = context.config.as_of_date.replace(month=1, day=1)
    phone_number = 1

    for contact_id in context.adult_contact_ids:
        if not context.fake.boolean(chance_of_getting_true=85):
            continue

        rows.append(
            {
                "id": context.stable_uuid("contact-phone-number", phone_number),
                "contact_id": contact_id,
                "phone_type": "mobile",
                "number": context.fake.phone_number(),
                "is_primary": True,
                "start_date": start_date,
                "end_date": None,
            }
        )
        phone_number += 1

        if context.fake.boolean(chance_of_getting_true=25):
            rows.append(
                {
                    "id": context.stable_uuid("contact-phone-number", phone_number),
                    "contact_id": contact_id,
                    "phone_type": context.fake.random_element(elements=("home", "work")),
                    "number": context.fake.phone_number(),
                    "is_primary": False,
                    "start_date": start_date,
                    "end_date": None,
                }
            )
            phone_number += 1

    return context.set_rows("contact_phone_numbers", rows)

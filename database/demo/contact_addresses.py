"""Demo data for contact addresses.

Adults only, one current home address each for most of the population -
matching contact_phone_numbers.py's sparsity approach.
"""

from demo.context import DemoContext


def populate(context: DemoContext) -> int:
    rows: list[dict[str, object]] = []
    start_date = context.config.as_of_date.replace(month=1, day=1)
    address_number = 1

    for contact_id in context.adult_contact_ids:
        if not context.fake.boolean(chance_of_getting_true=75):
            continue

        rows.append(
            {
                "id": context.stable_uuid("contact-address", address_number),
                "contact_id": contact_id,
                "address_type": "home",
                "line1": context.fake.street_address(),
                "line2": None,
                "city": context.fake.city(),
                "region": context.fake.county(),
                "postcode": context.fake.postcode(),
                "country": "United Kingdom",
                "start_date": start_date,
                "end_date": None,
            }
        )
        address_number += 1

    return context.set_rows("contact_addresses", rows)

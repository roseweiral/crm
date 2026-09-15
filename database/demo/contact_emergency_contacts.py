"""Demo data for contact emergency contacts.

A family's child always lists their family's parent (the same one
contact_family_units.py and contact_family_main_contacts.py pair them
with) as their emergency contact - a real family_relationship, not free
text. Adults (family parents included) get a plausible non-family
emergency contact for most of the population, matching the design's
"not every emergency contact is an existing family relationship" intent.
Each contact gets at most one entry (priority 1), so the
(contact_id, priority) and (contact_id, emergency_contact_id) unique
constraints are trivially satisfied.
"""

from demo.context import DemoContext

RELATIONSHIPS = ("Partner", "Sibling", "Friend", "Neighbour")


def populate(context: DemoContext) -> int:
    rows: list[dict[str, object]] = []
    entry_number = 1

    for index in range(context.config.family_count):
        rows.append(
            {
                "id": context.stable_uuid("contact-emergency-contact", entry_number),
                "contact_id": context.child_contact_ids[index],
                "emergency_contact_id": context.adult_contact_ids[index],
                "priority": 1,
                "relationship": "Parent",
            }
        )
        entry_number += 1

    for contact_id in context.adult_contact_ids:
        if not context.fake.boolean(chance_of_getting_true=80):
            continue

        candidates = [
            candidate_id
            for candidate_id in context.adult_contact_ids
            if candidate_id != contact_id
        ]
        rows.append(
            {
                "id": context.stable_uuid("contact-emergency-contact", entry_number),
                "contact_id": contact_id,
                "emergency_contact_id": context.fake.random_element(elements=candidates),
                "priority": 1,
                "relationship": context.fake.random_element(elements=RELATIONSHIPS),
            }
        )
        entry_number += 1

    return context.set_rows("contact_emergency_contacts", rows)

"""Demo data for contact awards."""

from datetime import timedelta

from demo.context import DemoContext


def populate(context: DemoContext) -> int:
    rows = []
    candidate_ids = context.adult_contact_ids + context.child_contact_ids
    context.fake.random.shuffle(candidate_ids)
    award_count = max(1, context.config.contact_count // 4)

    award_type_ids = tuple(context.award_type_ids.values())

    for award_number, contact_id in enumerate(candidate_ids[:award_count], start=1):
        nomination_date = context.config.as_of_date - timedelta(
            days=context.fake.random_int(min=30, max=365)
        )
        status = context.fake.random_element(
            elements=("nominated", "approved", "presented", "declined")
        )
        presented_date = (
            nomination_date + timedelta(days=context.fake.random_int(min=7, max=60))
            if status == "presented"
            else None
        )

        rows.append(
            {
                "id": context.stable_uuid("contact-award", award_number),
                "contact_id": contact_id,
                "award_type_id": award_type_ids[(award_number - 1) % len(award_type_ids)],
                "status": status,
                "nomination_date": nomination_date,
                "presented_date": presented_date,
                "notes": context.fake.sentence(nb_words=8),
            }
        )

    return context.set_rows("contact_awards", rows)

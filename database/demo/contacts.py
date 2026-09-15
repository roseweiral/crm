"""Demo data for contacts."""

from demo.context import DemoContext


# Real phonetic respellings for common en_GB Faker first names whose
# pronunciation isn't obvious from spelling. Deliberately small and
# curated rather than invented per-name nonsense - most contacts simply
# get no phonetic_name, matching real-world sparsity for this field.
PHONETIC_RESPELLINGS = {
    "siobhan": "shiv-AWN",
    "niamh": "NEEV",
    "saoirse": "SEER-sha",
    "aoife": "EE-fa",
    "caoimhe": "KEE-va",
    "eoin": "OH-in",
    "padraig": "POR-rig",
    "rhiannon": "ree-ANN-on",
    "sian": "SHAHN",
    "siân": "SHAHN",
    "cerys": "KEH-riss",
    "tegwen": "TEG-wen",
    "iolo": "YOL-oh",
    "bronwen": "BRON-wen",
    "euan": "YOO-an",
    "ewan": "YOO-an",
    "hamish": "HAY-mish",
    "rhona": "ROH-na",
    "deirdre": "DEER-dra",
}

GENDER_PRONOUNS = {
    "Male": "he/him",
    "Female": "she/her",
    "Non-binary": "they/them",
}


def _personal_details(context: DemoContext, first_name: str, is_adult: bool) -> dict[str, object]:
    date_of_birth = None
    if context.fake.boolean(chance_of_getting_true=70):
        if is_adult:
            date_of_birth = context.fake.date_of_birth(minimum_age=22, maximum_age=72)
        else:
            date_of_birth = context.fake.date_of_birth(minimum_age=5, maximum_age=17)

    preferred_name = None
    if context.fake.boolean(chance_of_getting_true=15):
        preferred_name = context.fake.first_name()

    phonetic_name = PHONETIC_RESPELLINGS.get(first_name.lower())

    gender = None
    pronouns = None
    if context.fake.boolean(chance_of_getting_true=50):
        gender = context.fake.random_element(
            elements=("Male", "Female", "Female", "Male", "Non-binary")
        )
        pronouns = GENDER_PRONOUNS[gender]

    return {
        "date_of_birth": date_of_birth,
        "preferred_name": preferred_name,
        "phonetic_name": phonetic_name,
        "pronouns": pronouns,
        "gender": gender,
    }


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
                **_personal_details(context, first_name, is_adult),
            }
        )

        target = context.adult_contact_ids if is_adult else context.child_contact_ids
        target.append(contact_id)

    return context.set_rows("contacts", rows)

"""Demo data for anonymous family units."""

from demo.context import DemoContext


def populate(context: DemoContext) -> int:
    rows = []

    for family_number in range(1, context.config.family_count + 1):
        family_unit_id = context.stable_uuid("family-unit", family_number)
        context.family_unit_ids.append(family_unit_id)
        rows.append({"id": family_unit_id})

    return context.set_rows("family_units", rows)

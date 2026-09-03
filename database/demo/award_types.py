"""Demo data for award types."""

from demo.context import DemoContext


def populate(context: DemoContext) -> int:
    context.award_type_ids = {
        "community_star": context.stable_uuid("award-type", "community-star"),
        "long_service": context.stable_uuid("award-type", "long-service"),
        "outstanding_contribution": context.stable_uuid(
            "award-type", "outstanding-contribution"
        ),
    }
    return context.set_rows(
        "award_types",
        [
            {"id": context.award_type_ids["community_star"], "name": "Community Star", "description": "Exceptional community contribution"},
            {"id": context.award_type_ids["long_service"], "name": "Long Service", "description": "Sustained service to the organisation"},
            {"id": context.award_type_ids["outstanding_contribution"], "name": "Outstanding Contribution", "description": "Work beyond normal expectations"},
        ],
    )

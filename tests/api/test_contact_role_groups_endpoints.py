"""HTTP contract tests for contact-role-group assignment endpoints."""

from uuid import UUID

import httpx
import pytest

from .support import API_URL, assert_first_page, database_rows, serialise


pytestmark = pytest.mark.contract
ASSIGNMENT_COLUMNS = (
    "id",
    "contact_id",
    "role_type_id",
    "group_id",
    "start_date",
    "end_date",
)


def test_get_contact_role_groups_returns_first_page() -> None:
    assert_first_page(
        path="/api/v1/contact-role-groups",
        table="contact_roles_groups",
        columns=ASSIGNMENT_COLUMNS,
        order_by="start_date, id",
    )


def test_get_contact_role_group_returns_matching_assignment() -> None:
    selected_columns = ", ".join(ASSIGNMENT_COLUMNS)
    assignment = database_rows(
        f"SELECT {selected_columns} FROM contact_roles_groups ORDER BY id LIMIT 1"
    )[0]

    response = httpx.get(
        f"{API_URL}/api/v1/contact-role-groups/{assignment['id']}", timeout=5
    )

    assert response.status_code == 200
    assert response.json() == serialise(assignment)


def test_get_contact_role_group_returns_404_for_unknown_uuid() -> None:
    unknown_id = UUID("00000000-0000-0000-0000-000000000000")

    response = httpx.get(
        f"{API_URL}/api/v1/contact-role-groups/{unknown_id}", timeout=5
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Contact role group not found"}


def test_get_contact_role_group_rejects_malformed_uuid() -> None:
    response = httpx.get(
        f"{API_URL}/api/v1/contact-role-groups/not-a-uuid", timeout=5
    )

    assert response.status_code == 422

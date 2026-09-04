"""HTTP contract tests for contact-role-group assignment endpoints."""

from uuid import UUID

import httpx
import pytest

from .support import API_URL, database_rows, serialise


pytestmark = pytest.mark.contract
ASSIGNMENT_COLUMNS = """
  crg.id,
  crg.contact_id,
  c.first_name AS contact_first_name,
  c.last_name AS contact_last_name,
  crg.role_type_id,
  rt.name AS role_type_name,
  crg.group_id,
  g.name AS group_name,
  crg.start_date,
  crg.end_date
"""


def expected_assignments(
    where: str = "",
    parameters: tuple[UUID, ...] = (),
) -> list[dict]:
    return database_rows(
        f"""
        SELECT {ASSIGNMENT_COLUMNS}
        FROM contact_roles_groups crg
        JOIN contacts c ON c.id = crg.contact_id
        JOIN role_types rt ON rt.id = crg.role_type_id
        JOIN groups g ON g.id = crg.group_id
        {where}
        ORDER BY crg.start_date, crg.id
        LIMIT 25
        """,
        parameters,
    )


def test_get_contact_role_groups_returns_first_page() -> None:
    expected = expected_assignments()
    total = database_rows(
        "SELECT count(*) AS total FROM contact_roles_groups"
    )[0]["total"]

    response = httpx.get(f"{API_URL}/api/v1/contact-role-groups", timeout=5)

    assert response.status_code == 200
    assert response.json() == {
        "items": serialise(expected),
        "page": 1,
        "page_size": 25,
        "total": total,
    }


def test_get_contact_role_group_returns_matching_assignment() -> None:
    assignment = database_rows(
        f"""
        SELECT {ASSIGNMENT_COLUMNS}, crg.created_at, crg.modified_at
        FROM contact_roles_groups crg
        JOIN contacts c ON c.id = crg.contact_id
        JOIN role_types rt ON rt.id = crg.role_type_id
        JOIN groups g ON g.id = crg.group_id
        ORDER BY crg.id
        LIMIT 1
        """
    )[0]

    response = httpx.get(
        f"{API_URL}/api/v1/contact-role-groups/{assignment['id']}", timeout=5
    )

    assert response.status_code == 200
    assert response.json() == serialise(assignment)


@pytest.mark.parametrize("filter_name", ("contact_id", "group_id", "role_type_id"))
def test_get_contact_role_groups_filters_by_related_uuid(filter_name: str) -> None:
    column_name = filter_name
    selected = database_rows(
        f"SELECT {column_name} FROM contact_roles_groups ORDER BY id LIMIT 1"
    )[0][column_name]
    expected = expected_assignments(f"WHERE crg.{column_name} = %s", (selected,))

    response = httpx.get(
        f"{API_URL}/api/v1/contact-role-groups",
        params={filter_name: str(selected)},
        timeout=5,
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": serialise(expected),
        "page": 1,
        "page_size": 25,
        "total": len(expected),
    }


def test_get_contact_role_groups_combines_uuid_filters() -> None:
    selected = database_rows(
        """
        SELECT contact_id, group_id, role_type_id
        FROM contact_roles_groups
        ORDER BY id
        LIMIT 1
        """
    )[0]
    expected = expected_assignments(
        """
        WHERE crg.contact_id = %s
          AND crg.group_id = %s
          AND crg.role_type_id = %s
        """,
        (selected["contact_id"], selected["group_id"], selected["role_type_id"]),
    )

    response = httpx.get(
        f"{API_URL}/api/v1/contact-role-groups",
        params={key: str(value) for key, value in selected.items()},
        timeout=5,
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": serialise(expected),
        "page": 1,
        "page_size": 25,
        "total": len(expected),
    }


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

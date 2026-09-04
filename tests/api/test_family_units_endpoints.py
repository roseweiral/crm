"""HTTP contract tests for family-unit endpoints."""

from uuid import UUID

import httpx
import pytest

from .support import API_URL, assert_first_page, database_rows, serialise


pytestmark = pytest.mark.contract


def test_get_family_units_returns_first_page() -> None:
    assert_first_page(
        path="/api/v1/family-units",
        table="family_units",
        columns=("id",),
        order_by="id",
    )


def test_get_family_unit_returns_all_members_and_relationships() -> None:
    family_unit = database_rows("SELECT id FROM family_units ORDER BY id LIMIT 1")[0]
    members = database_rows(
        """
        SELECT
          c.id AS contact_id,
          c.first_name,
          c.last_name,
          cfu.relationship
        FROM contact_family_units cfu
        JOIN contacts c ON c.id = cfu.contact_id
        WHERE cfu.family_unit_id = %s
        ORDER BY c.last_name, c.first_name, c.id
        """,
        (family_unit["id"],),
    )

    response = httpx.get(
        f"{API_URL}/api/v1/family-units/{family_unit['id']}", timeout=5
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": str(family_unit["id"]),
        "members": serialise(members),
    }


def test_get_family_unit_returns_404_for_unknown_uuid() -> None:
    unknown_id = UUID("00000000-0000-0000-0000-000000000000")

    response = httpx.get(f"{API_URL}/api/v1/family-units/{unknown_id}", timeout=5)

    assert response.status_code == 404
    assert response.json() == {"detail": "Family unit not found"}


def test_get_family_unit_rejects_malformed_uuid() -> None:
    response = httpx.get(f"{API_URL}/api/v1/family-units/not-a-uuid", timeout=5)

    assert response.status_code == 422

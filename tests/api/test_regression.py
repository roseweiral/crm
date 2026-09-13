"""Regression coverage for behavior shared by the collection endpoints."""

from math import ceil
from uuid import UUID

import httpx
import pytest

from .support import API_URL, database_rows, serialise


pytestmark = pytest.mark.regression

COLLECTION_PATHS = (
    "/api/v1/contacts",
    "/api/v1/family-units",
    "/api/v1/role-types",
    "/api/v1/group-types",
    "/api/v1/groups",
    "/api/v1/contact-role-groups",
)


@pytest.mark.parametrize("path", COLLECTION_PATHS)
def test_collection_pagination_returns_every_record_once(path: str, records) -> None:
    if path == "/api/v1/contacts":
        for index in range(105):
            records("contacts", first_name="Pagination", last_name=f"{index:03d}")
    full_response = httpx.get(f"{API_URL}{path}", params={"page_size": 100}, timeout=5)

    assert full_response.status_code == 200
    full_page = full_response.json()
    table, order = {
        "/api/v1/contacts": ("contacts", "last_name, first_name, id"),
        "/api/v1/family-units": ("family_units", "id"),
        "/api/v1/role-types": ("role_types", "name, id"),
        "/api/v1/group-types": ("group_types", "name, id"),
        "/api/v1/groups": ("groups", "name, id"),
        "/api/v1/contact-role-groups": ("contact_roles_groups", "start_date, id"),
    }[path]
    expected_ids = [
        str(row["id"])
        for row in database_rows(f"SELECT id FROM {table} ORDER BY {order}")
    ]
    assert full_page["total"] == len(expected_ids)
    assert [item["id"] for item in full_page["items"]] == expected_ids[:100]
    page_size = 2
    page_count = ceil(full_page["total"] / page_size)
    paged_items = []

    for page_number in range(1, page_count + 1):
        response = httpx.get(
            f"{API_URL}{path}",
            params={"page": page_number, "page_size": page_size},
            timeout=5,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["page"] == page_number
        assert payload["page_size"] == page_size
        assert payload["total"] == full_page["total"]
        paged_items.extend(payload["items"])

    assert [item["id"] for item in paged_items] == expected_ids
    assert len({item["id"] for item in paged_items}) == full_page["total"]


@pytest.mark.parametrize("path", COLLECTION_PATHS)
def test_collection_page_beyond_last_page_is_empty(path: str) -> None:
    first_response = httpx.get(f"{API_URL}{path}", timeout=5)
    assert first_response.status_code == 200
    total = first_response.json()["total"]
    page_size = 5
    page_number = ceil(total / page_size) + 1

    response = httpx.get(
        f"{API_URL}{path}",
        params={"page": page_number, "page_size": page_size},
        timeout=5,
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "page": page_number,
        "page_size": page_size,
        "total": total,
    }


@pytest.mark.parametrize("path", COLLECTION_PATHS)
@pytest.mark.parametrize(
    "parameters",
    ({"page": 0}, {"page_size": 0}, {"page_size": 101}),
    ids=("page-below-minimum", "page-size-below-minimum", "page-size-above-maximum"),
)
def test_collection_rejects_invalid_pagination(
    path: str, parameters: dict[str, int]
) -> None:
    response = httpx.get(f"{API_URL}{path}", params=parameters, timeout=5)

    assert response.status_code == 422


def test_default_demo_dataset_keeps_expected_core_records() -> None:
    expected_totals = {
        "/api/v1/contacts": 60,
        "/api/v1/family-units": 15,
        "/api/v1/role-types": 3,
        "/api/v1/group-types": 5,
        "/api/v1/groups": 11,
        "/api/v1/contact-role-groups": 23,
    }

    for path, expected_total in expected_totals.items():
        response = httpx.get(f"{API_URL}{path}", params={"page_size": 100}, timeout=5)
        assert response.status_code == 200
        assert response.json()["total"] == expected_total, path

    role_response = httpx.get(
        f"{API_URL}/api/v1/role-types", params={"page_size": 100}, timeout=5
    )
    group_type_response = httpx.get(
        f"{API_URL}/api/v1/group-types", params={"page_size": 100}, timeout=5
    )
    role_names = [item["name"] for item in role_response.json()["items"]]
    group_type_names = [item["name"] for item in group_type_response.json()["items"]]

    assert role_names == [
        "Area Manager",
        "Group Helper",
        "Group Leader",
    ]
    assert group_type_names == [
        "City",
        "County",
        "Group",
        "HQ",
        "Town",
    ]


@pytest.mark.parametrize("filter_name", ("contact_id", "group_id", "role_type_id"))
def test_assignment_filter_with_no_matches_returns_an_empty_page(
    filter_name: str,
) -> None:
    unknown_id = UUID("00000000-0000-0000-0000-000000000000")

    response = httpx.get(
        f"{API_URL}/api/v1/contact-role-groups",
        params={filter_name: str(unknown_id)},
        timeout=5,
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "page": 1,
        "page_size": 25,
        "total": 0,
    }


def test_assignment_filter_preserves_pagination_and_human_readable_fields() -> None:
    role_type = database_rows("SELECT id FROM role_types WHERE name = 'Group Helper'")[
        0
    ]
    expected = database_rows(
        """
        SELECT
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
        FROM contact_roles_groups crg
        JOIN contacts c ON c.id = crg.contact_id
        JOIN role_types rt ON rt.id = crg.role_type_id
        JOIN groups g ON g.id = crg.group_id
        WHERE crg.role_type_id = %s
        ORDER BY crg.start_date, crg.id
        LIMIT 2 OFFSET 2
        """,
        (role_type["id"],),
    )
    total = database_rows(
        "SELECT count(*) AS total FROM contact_roles_groups WHERE role_type_id = %s",
        (role_type["id"],),
    )[0]["total"]

    response = httpx.get(
        f"{API_URL}/api/v1/contact-role-groups",
        params={
            "role_type_id": str(role_type["id"]),
            "page": 2,
            "page_size": 2,
        },
        timeout=5,
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": serialise(expected),
        "page": 2,
        "page_size": 2,
        "total": total,
    }

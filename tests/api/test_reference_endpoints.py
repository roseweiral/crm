"""HTTP contract tests for role-type, group-type, and group endpoints."""

from dataclasses import dataclass
from uuid import UUID

import httpx
import pytest

from .support import API_URL, assert_first_page, database_rows, serialise


pytestmark = pytest.mark.contract


@dataclass(frozen=True)
class ResourceContract:
    path: str
    table: str
    columns: tuple[str, ...]
    order_by: str
    not_found_detail: str


RESOURCE_CONTRACTS = (
    ResourceContract(
        path="/api/v1/role-types",
        table="role_types",
        columns=("id", "name", "description"),
        order_by="name, id",
        not_found_detail="Role type not found",
    ),
    ResourceContract(
        path="/api/v1/group-types",
        table="group_types",
        columns=("id", "name", "description"),
        order_by="name, id",
        not_found_detail="Group type not found",
    ),
)


@pytest.mark.parametrize("resource", RESOURCE_CONTRACTS, ids=lambda item: item.table)
def test_get_resource_returns_first_page(resource: ResourceContract) -> None:
    assert_first_page(
        path=resource.path,
        table=resource.table,
        columns=resource.columns,
        order_by=resource.order_by,
    )


@pytest.mark.parametrize("resource", RESOURCE_CONTRACTS, ids=lambda item: item.table)
def test_get_resource_by_id_returns_matching_record(resource: ResourceContract) -> None:
    selected_columns = ", ".join((*resource.columns, "created_at", "modified_at"))
    record = database_rows(
        f"SELECT {selected_columns} FROM {resource.table} ORDER BY id LIMIT 1"
    )[0]

    response = httpx.get(f"{API_URL}{resource.path}/{record['id']}", timeout=5)

    assert response.status_code == 200
    assert response.json() == serialise(record)


@pytest.mark.parametrize("resource", RESOURCE_CONTRACTS, ids=lambda item: item.table)
def test_get_resource_returns_404_for_unknown_uuid(resource: ResourceContract) -> None:
    unknown_id = UUID("00000000-0000-0000-0000-000000000000")

    response = httpx.get(f"{API_URL}{resource.path}/{unknown_id}", timeout=5)

    assert response.status_code == 404
    assert response.json() == {"detail": resource.not_found_detail}


@pytest.mark.parametrize("resource", RESOURCE_CONTRACTS, ids=lambda item: item.table)
def test_get_resource_rejects_malformed_uuid(resource: ResourceContract) -> None:
    response = httpx.get(f"{API_URL}{resource.path}/not-a-uuid", timeout=5)

    assert response.status_code == 422


GROUP_COLUMNS = """
  g.id,
  g.group_type_id,
  gt.name AS group_type_name,
  g.name,
  g.description,
  g.parent_id,
  parent.name AS parent_name
"""


def test_get_groups_returns_names_for_group_type_and_parent() -> None:
    expected = database_rows(
        f"""
        SELECT {GROUP_COLUMNS}
        FROM groups g
        JOIN group_types gt ON gt.id = g.group_type_id
        LEFT JOIN groups parent ON parent.id = g.parent_id
        ORDER BY g.name, g.id
        LIMIT 25
        """
    )
    total = database_rows("SELECT count(*) AS total FROM groups")[0]["total"]

    response = httpx.get(f"{API_URL}/api/v1/groups", timeout=5)

    assert response.status_code == 200
    assert response.json() == {
        "items": serialise(expected),
        "page": 1,
        "page_size": 25,
        "total": total,
    }


def test_get_group_by_id_returns_names_and_timestamps() -> None:
    group = database_rows(
        f"""
        SELECT {GROUP_COLUMNS}, g.created_at, g.modified_at
        FROM groups g
        JOIN group_types gt ON gt.id = g.group_type_id
        LEFT JOIN groups parent ON parent.id = g.parent_id
        ORDER BY g.id
        LIMIT 1
        """
    )[0]

    response = httpx.get(f"{API_URL}/api/v1/groups/{group['id']}", timeout=5)

    assert response.status_code == 200
    assert response.json() == serialise(group)


def test_get_group_returns_404_for_unknown_uuid() -> None:
    unknown_id = UUID("00000000-0000-0000-0000-000000000000")

    response = httpx.get(f"{API_URL}/api/v1/groups/{unknown_id}", timeout=5)

    assert response.status_code == 404
    assert response.json() == {"detail": "Group not found"}


def test_get_group_rejects_malformed_uuid() -> None:
    response = httpx.get(f"{API_URL}/api/v1/groups/not-a-uuid", timeout=5)

    assert response.status_code == 422

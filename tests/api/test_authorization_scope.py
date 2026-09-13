"""Explicit authorization facts independent of demo users and group structure."""

from datetime import date, timedelta
from uuid import uuid4

import httpx
import pytest

from .support import API_URL, database_rows

pytestmark = pytest.mark.regression


@pytest.fixture
def hierarchy(records):
    group_type = records("group_types", name="Test hierarchy")
    root = records("groups", group_type_id=group_type["id"], name="Root")
    child = records(
        "groups", group_type_id=group_type["id"], name="Child", parent_id=root["id"]
    )
    grandchild = records(
        "groups",
        group_type_id=group_type["id"],
        name="Grandchild",
        parent_id=child["id"],
    )
    unrelated = records("groups", group_type_id=group_type["id"], name="Unrelated")
    return root, child, grandchild, unrelated


@pytest.mark.parametrize("role", ["Group Leader", "Area Manager"])
def test_leader_sees_descendants_but_not_other_branches(
    records, person, session_token, hierarchy, role
):
    contact, account = person()
    role_id = database_rows("SELECT id FROM role_types WHERE name = %s", (role,))[0][
        "id"
    ]
    root, child, grandchild, unrelated = hierarchy
    records(
        "contact_roles_groups",
        contact_id=contact["id"],
        group_id=root["id"],
        role_type_id=role_id,
        start_date=date.today(),
    )
    with httpx.Client(cookies={"crm_session": session_token(account["id"])}) as client:
        response = client.get(f"{API_URL}/api/v1/groups", params={"page_size": 100})
        assert response.status_code == 200
        assert {item["id"] for item in response.json()["items"]} == {
            str(g["id"]) for g in (root, child, grandchild)
        }
        assert response.json()["total"] == 3
        assert (
            client.get(f"{API_URL}/api/v1/groups/{grandchild['id']}").status_code == 200
        )
        assert (
            client.get(f"{API_URL}/api/v1/groups/{unrelated['id']}").status_code == 404
        )


def test_parent_sees_their_family_but_not_unrelated_contacts(
    records, person, session_token
):
    parent, account = person()
    child, _ = person()
    outsider, _ = person()
    family = records("family_units", id=uuid4())
    records(
        "contact_family_units",
        contact_id=parent["id"],
        family_unit_id=family["id"],
        relationship="parent",
    )
    records(
        "contact_family_units",
        contact_id=child["id"],
        family_unit_id=family["id"],
        relationship="child",
    )
    with httpx.Client(cookies={"crm_session": session_token(account["id"])}) as client:
        contacts = client.get(f"{API_URL}/api/v1/contacts")
        families = client.get(f"{API_URL}/api/v1/family-units")
        assert contacts.status_code == families.status_code == 200
        assert {item["id"] for item in contacts.json()["items"]} == {
            str(parent["id"]),
            str(child["id"]),
        }
        assert [item["id"] for item in families.json()["items"]] == [str(family["id"])]
        assert (
            client.get(f"{API_URL}/api/v1/contacts/{outsider['id']}").status_code == 404
        )
        assert (
            client.get(f"{API_URL}/api/v1/family-units/{family['id']}").status_code
            == 200
        )


def test_child_sees_only_self_and_cannot_access_existing_private_details(
    records, person, session_token, hierarchy
):
    child, account = person()
    parent, _ = person()
    family = records("family_units", id=uuid4())
    records(
        "contact_family_units",
        contact_id=child["id"],
        family_unit_id=family["id"],
        relationship="child",
    )
    records(
        "contact_family_units",
        contact_id=parent["id"],
        family_unit_id=family["id"],
        relationship="parent",
    )
    group = hierarchy[0]
    role_id = database_rows("SELECT id FROM role_types WHERE name = 'Group Helper'")[0][
        "id"
    ]
    assignment = records(
        "contact_roles_groups",
        contact_id=parent["id"],
        group_id=group["id"],
        role_type_id=role_id,
        start_date=date.today(),
    )
    with httpx.Client(cookies={"crm_session": session_token(account["id"])}) as client:
        contacts = client.get(f"{API_URL}/api/v1/contacts")
        assert contacts.status_code == 200
        assert [item["id"] for item in contacts.json()["items"]] == [str(child["id"])]
        for path, record in [
            ("contacts", parent),
            ("family-units", family),
            ("groups", group),
            ("contact-role-groups", assignment),
        ]:
            assert (
                client.get(f"{API_URL}/api/v1/{path}/{record['id']}").status_code == 404
            )
        for path in ("family-units", "groups", "contact-role-groups"):
            response = client.get(f"{API_URL}/api/v1/{path}")
            assert response.status_code == 200
            assert response.json()["items"] == []
            assert response.json()["total"] == 0
        assert (
            client.post(
                f"{API_URL}/api/v1/invitations", json={"contact_id": str(parent["id"])}
            ).status_code
            == 403
        )


@pytest.mark.parametrize("period", ["future", "expired"])
def test_inactive_group_role_grants_no_group_access(
    records, person, session_token, hierarchy, period
):
    contact, account = person()
    today = date.today()
    role_id = database_rows("SELECT id FROM role_types WHERE name = 'Group Leader'")[0][
        "id"
    ]
    records(
        "contact_roles_groups",
        contact_id=contact["id"],
        group_id=hierarchy[0]["id"],
        role_type_id=role_id,
        start_date=today + timedelta(days=1)
        if period == "future"
        else today - timedelta(days=2),
        end_date=None if period == "future" else today - timedelta(days=1),
    )
    with httpx.Client(cookies={"crm_session": session_token(account["id"])}) as client:
        response = client.get(f"{API_URL}/api/v1/groups")
        assert response.status_code == 200
        assert response.json()["total"] == 0

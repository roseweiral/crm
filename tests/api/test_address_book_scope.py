"""Regression coverage for who does and does not appear in the address book.

Complements test_address_book_endpoints.py's HTTP contract tests by proving the
eligibility rules from documents/family-and-directory-design.md: date windows,
hidden flags, contact status, and — the point of this whole feature — that the
address book connects people across branches the hierarchy-scoped endpoints
deliberately keep apart.
"""

from datetime import date, timedelta
from uuid import uuid4

import httpx
import psycopg
import pytest

from .support import API_URL, DATABASE_URL, database_rows


pytestmark = pytest.mark.regression


def role_type_id(name: str):
    return database_rows("SELECT id FROM role_types WHERE name = %s", (name,))[0]["id"]


def global_access_role_id():
    return database_rows(
        "SELECT id FROM access_roles WHERE is_global = true ORDER BY id LIMIT 1"
    )[0]["id"]


@pytest.fixture
def group(records):
    group_type = records("group_types", name=f"Address book scope type {uuid4()}")
    return records(
        "groups", group_type_id=group_type["id"], name=f"Address book scope group {uuid4()}"
    )


@pytest.fixture
def viewer(records, person, session_token):
    """A Global-System-Administrator viewer, so the candidate's own eligibility
    is what's under test, not the viewer's."""
    _, account = person()
    records(
        "user_access_role_assignments",
        user_account_id=account["id"],
        access_role_id=global_access_role_id(),
        start_date=date.today(),
    )
    return session_token(account["id"])


def visible_contact_ids(token, **params):
    response = httpx.get(
        f"{API_URL}/api/v1/address-book",
        params={"page_size": 100, **params},
        cookies={"crm_session": token},
        timeout=5,
    )
    assert response.status_code == 200
    return {item["contact_id"] for item in response.json()["items"]}


# --- Eligibility to appear ---------------------------------------------------


@pytest.mark.parametrize("period", ["future", "expired"])
def test_inactive_role_grants_no_directory_presence(records, person, group, viewer, period):
    contact, _ = person()
    today = date.today()
    records(
        "contact_roles_groups",
        contact_id=contact["id"],
        role_type_id=role_type_id("Group Leader"),
        group_id=group["id"],
        start_date=today + timedelta(days=1) if period == "future" else today - timedelta(days=2),
        end_date=None if period == "future" else today - timedelta(days=1),
    )
    assert str(contact["id"]) not in visible_contact_ids(viewer)


def test_archived_contact_is_excluded_even_with_an_active_role(records, person, group, viewer):
    contact, _ = person()
    records(
        "contact_roles_groups",
        contact_id=contact["id"],
        role_type_id=role_type_id("Group Leader"),
        group_id=group["id"],
        start_date=date.today(),
    )
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(
            "UPDATE contacts SET status = 'archived' WHERE id = %s", (contact["id"],)
        )
    assert str(contact["id"]) not in visible_contact_ids(viewer)


def test_a_role_type_outside_the_eligible_set_grants_no_directory_access(
    records, person, group, viewer
):
    contact, _ = person()
    other_role_type = records("role_types", name=f"Committee Member {uuid4()}")
    records(
        "contact_roles_groups",
        contact_id=contact["id"],
        role_type_id=other_role_type["id"],
        group_id=group["id"],
        start_date=date.today(),
    )
    assert str(contact["id"]) not in visible_contact_ids(viewer)


def test_hiding_every_eligible_role_removes_the_contact_from_the_directory(
    records, person, group, viewer
):
    contact, _ = person()
    records(
        "contact_roles_groups",
        contact_id=contact["id"],
        role_type_id=role_type_id("Group Leader"),
        group_id=group["id"],
        start_date=date.today(),
        hidden_from_directory=True,
    )
    assert str(contact["id"]) not in visible_contact_ids(viewer)


def test_a_contact_still_appears_via_a_non_hidden_role(records, person, group, viewer):
    contact, _ = person()
    records(
        "contact_roles_groups",
        contact_id=contact["id"],
        role_type_id=role_type_id("Group Leader"),
        group_id=group["id"],
        start_date=date.today(),
        hidden_from_directory=True,
    )
    records(
        "contact_roles_groups",
        contact_id=contact["id"],
        role_type_id=role_type_id("Group Helper"),
        group_id=group["id"],
        start_date=date(2000, 1, 1),
    )
    assert str(contact["id"]) in visible_contact_ids(viewer)


def test_self_hide_removes_the_contact_regardless_of_roles(records, person, group, viewer):
    contact, _ = person()
    records(
        "contact_roles_groups",
        contact_id=contact["id"],
        role_type_id=role_type_id("Area Manager"),
        group_id=group["id"],
        start_date=date.today(),
    )
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(
            "UPDATE contacts SET hidden_from_directory = true WHERE id = %s",
            (contact["id"],),
        )
    assert str(contact["id"]) not in visible_contact_ids(viewer)


# --- Non-members are rejected, not just filtered ----------------------------


def test_an_ordinary_contact_with_no_role_is_rejected(person, session_token):
    _, account = person()
    response = httpx.get(
        f"{API_URL}/api/v1/address-book",
        cookies={"crm_session": session_token(account["id"])},
        timeout=5,
    )
    assert response.status_code == 403


def test_a_parent_with_no_organisational_role_is_rejected(records, person, session_token):
    """A family relationship alone must not grant address-book access — only an
    organisational or global access role does (documents/family-and-directory-design.md)."""
    parent, account = person()
    family = records("family_units", id=uuid4())
    records(
        "contact_family_units",
        contact_id=parent["id"],
        family_unit_id=family["id"],
        relationship="parent",
    )
    response = httpx.get(
        f"{API_URL}/api/v1/address-book",
        cookies={"crm_session": session_token(account["id"])},
        timeout=5,
    )
    assert response.status_code == 403


# --- The point of the feature: cross-branch visibility ----------------------


def test_eligible_adults_see_each_other_across_unrelated_branches(records, person, session_token):
    branch_a_type = records("group_types", name=f"Branch A type {uuid4()}")
    branch_a = records("groups", group_type_id=branch_a_type["id"], name=f"Branch A {uuid4()}")
    branch_b_type = records("group_types", name=f"Branch B type {uuid4()}")
    branch_b = records("groups", group_type_id=branch_b_type["id"], name=f"Branch B {uuid4()}")

    viewer, viewer_account = person()
    records(
        "contact_roles_groups",
        contact_id=viewer["id"],
        role_type_id=role_type_id("Group Leader"),
        group_id=branch_a["id"],
        start_date=date.today(),
    )
    other, _ = person()
    records(
        "contact_roles_groups",
        contact_id=other["id"],
        role_type_id=role_type_id("Area Manager"),
        group_id=branch_b["id"],
        start_date=date.today(),
    )

    viewer_token = session_token(viewer_account["id"])

    # The existing hierarchy-scoped endpoint keeps the two branches apart...
    contacts_detail = httpx.get(
        f"{API_URL}/api/v1/contacts/{other['id']}",
        cookies={"crm_session": viewer_token},
        timeout=5,
    )
    assert contacts_detail.status_code == 404

    # ...but the address book, built for exactly this case, connects them.
    assert str(other["id"]) in visible_contact_ids(viewer_token)


# --- group_id filter -----------------------------------------------------


def test_group_id_filter_includes_the_named_group_and_excludes_others(
    records, person, group, viewer
):
    contact, _ = person()
    records(
        "contact_roles_groups",
        contact_id=contact["id"],
        role_type_id=role_type_id("Group Leader"),
        group_id=group["id"],
        start_date=date.today(),
    )
    other_type = records("group_types", name=f"Filter control type {uuid4()}")
    other_group = records("groups", group_type_id=other_type["id"], name=f"Filter control {uuid4()}")
    outside, _ = person()
    records(
        "contact_roles_groups",
        contact_id=outside["id"],
        role_type_id=role_type_id("Group Leader"),
        group_id=other_group["id"],
        start_date=date.today(),
    )
    visible = visible_contact_ids(viewer, group_id=group["id"])
    assert str(contact["id"]) in visible
    assert str(outside["id"]) not in visible


def test_group_id_filter_includes_descendant_groups_and_excludes_others(
    records, person, viewer
):
    hierarchy_type = records("group_types", name=f"Address book filter type {uuid4()}")
    root = records("groups", group_type_id=hierarchy_type["id"], name=f"Root {uuid4()}")
    child = records(
        "groups",
        group_type_id=hierarchy_type["id"],
        name=f"Child {uuid4()}",
        parent_id=root["id"],
    )
    sibling_type = records("group_types", name=f"Filter sibling type {uuid4()}")
    sibling_root = records("groups", group_type_id=sibling_type["id"], name=f"Sibling root {uuid4()}")

    contact, _ = person()
    records(
        "contact_roles_groups",
        contact_id=contact["id"],
        role_type_id=role_type_id("Group Leader"),
        group_id=child["id"],
        start_date=date.today(),
    )
    outside, _ = person()
    records(
        "contact_roles_groups",
        contact_id=outside["id"],
        role_type_id=role_type_id("Group Leader"),
        group_id=sibling_root["id"],
        start_date=date.today(),
    )
    visible = visible_contact_ids(viewer, group_id=root["id"])
    assert str(contact["id"]) in visible
    assert str(outside["id"]) not in visible


def test_group_id_filter_excludes_an_unrelated_branch(records, person, viewer):
    branch_a_type = records("group_types", name=f"Filter branch A type {uuid4()}")
    branch_a = records("groups", group_type_id=branch_a_type["id"], name=f"Filter branch A {uuid4()}")
    branch_b_type = records("group_types", name=f"Filter branch B type {uuid4()}")
    branch_b = records("groups", group_type_id=branch_b_type["id"], name=f"Filter branch B {uuid4()}")

    other, _ = person()
    records(
        "contact_roles_groups",
        contact_id=other["id"],
        role_type_id=role_type_id("Area Manager"),
        group_id=branch_b["id"],
        start_date=date.today(),
    )
    assert str(other["id"]) not in visible_contact_ids(viewer, group_id=branch_a["id"])

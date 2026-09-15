"""HTTP contract tests for the organisation-wide address book."""

from datetime import date
from uuid import uuid4

import httpx
import pytest

from .support import API_URL, database_rows


pytestmark = pytest.mark.contract


def role_type_id(name: str):
    return database_rows("SELECT id FROM role_types WHERE name = %s", (name,))[0]["id"]


def global_access_role():
    return database_rows(
        "SELECT id, name FROM access_roles WHERE is_global = true ORDER BY id LIMIT 1"
    )[0]


@pytest.fixture
def group(records):
    group_type = records("group_types", name=f"Address book group type {uuid4()}")
    return records(
        "groups", group_type_id=group_type["id"], name=f"Address book group {uuid4()}"
    )


@pytest.fixture
def hierarchy(records):
    group_type = records("group_types", name=f"Address book hierarchy {uuid4()}")
    root = records("groups", group_type_id=group_type["id"], name=f"Root {uuid4()}")
    child = records(
        "groups",
        group_type_id=group_type["id"],
        name=f"Child {uuid4()}",
        parent_id=root["id"],
    )
    return root, child


@pytest.fixture
def eligible_viewer(records, person, session_token, group):
    """An address-book-eligible contact, for tests that only need a valid viewer."""
    contact, account = person()
    records(
        "contact_roles_groups",
        contact_id=contact["id"],
        role_type_id=role_type_id("Group Leader"),
        group_id=group["id"],
        start_date=date.today(),
    )
    return session_token(account["id"])


@pytest.fixture
def caller(callback_client):
    """A real routed client with the write-security headers already set."""
    client, _ = callback_client
    client.headers.update({"Origin": "http://localhost:5173", "X-CRM-CSRF": "1"})
    return client


def tag(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers.get("etag"), "Detail GET must expose an ETag"
    return response.headers["etag"]


# --- GET /api/v1/address-book -----------------------------------------------


def test_address_book_requires_a_session():
    with httpx.Client() as client:
        response = client.get(f"{API_URL}/api/v1/address-book", timeout=5)
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_address_book_rejects_a_contact_with_no_eligible_role(person, session_token):
    _, account = person()
    response = httpx.get(
        f"{API_URL}/api/v1/address-book",
        cookies={"crm_session": session_token(account["id"])},
        timeout=5,
    )
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["Group Leader", "Group Helper", "Area Manager"])
def test_address_book_admits_any_adult_organisational_role(
    records, person, session_token, group, role
):
    contact, account = person()
    records(
        "contact_roles_groups",
        contact_id=contact["id"],
        role_type_id=role_type_id(role),
        group_id=group["id"],
        start_date=date.today(),
    )
    response = httpx.get(
        f"{API_URL}/api/v1/address-book",
        cookies={"crm_session": session_token(account["id"])},
        timeout=5,
    )
    assert response.status_code == 200
    assert set(response.json()) == {"items", "page", "page_size", "total"}


def test_address_book_admits_a_global_access_role(records, person, session_token):
    _, account = person()
    records(
        "user_access_role_assignments",
        user_account_id=account["id"],
        access_role_id=global_access_role()["id"],
        start_date=date.today(),
    )
    response = httpx.get(
        f"{API_URL}/api/v1/address-book",
        cookies={"crm_session": session_token(account["id"])},
        timeout=5,
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    "parameters",
    ({"page": 0}, {"page_size": 0}, {"page_size": 101}),
    ids=("page-below-minimum", "page-size-below-minimum", "page-size-above-maximum"),
)
def test_address_book_rejects_invalid_pagination(eligible_viewer, parameters):
    response = httpx.get(
        f"{API_URL}/api/v1/address-book",
        params=parameters,
        cookies={"crm_session": eligible_viewer},
        timeout=5,
    )
    assert response.status_code == 422


def test_address_book_group_id_filter_rejects_malformed_uuid(eligible_viewer):
    response = httpx.get(
        f"{API_URL}/api/v1/address-book",
        params={"group_id": "not-a-uuid"},
        cookies={"crm_session": eligible_viewer},
        timeout=5,
    )
    assert response.status_code == 422


def test_address_book_group_id_filter_with_unknown_group_returns_empty_page(eligible_viewer):
    response = httpx.get(
        f"{API_URL}/api/v1/address-book",
        params={"group_id": str(uuid4())},
        cookies={"crm_session": eligible_viewer},
        timeout=5,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_address_book_entry_shows_name_contact_and_group_role(
    records, person, session_token, group
):
    contact, account = person()
    records(
        "contact_roles_groups",
        contact_id=contact["id"],
        role_type_id=role_type_id("Group Leader"),
        group_id=group["id"],
        start_date=date.today(),
    )
    response = httpx.get(
        f"{API_URL}/api/v1/address-book",
        params={"page_size": 100},
        cookies={"crm_session": session_token(account["id"])},
        timeout=5,
    )
    entry = next(
        item
        for item in response.json()["items"]
        if item["contact_id"] == str(contact["id"])
    )
    assert entry["first_name"] == contact["first_name"]
    assert entry["last_name"] == contact["last_name"]
    assert entry["email"] == contact["email"]
    assert entry["roles"] == [
        {
            "kind": "group_role",
            "role_type_name": "Group Leader",
            "group_id": str(group["id"]),
            "group_name": group["name"],
            "group_path": [{"id": str(group["id"]), "name": group["name"]}],
        }
    ]


def test_address_book_entry_shows_an_access_role(records, person, session_token):
    contact, account = person()
    access_role = global_access_role()
    records(
        "user_access_role_assignments",
        user_account_id=account["id"],
        access_role_id=access_role["id"],
        start_date=date.today(),
    )
    response = httpx.get(
        f"{API_URL}/api/v1/address-book",
        params={"page_size": 100},
        cookies={"crm_session": session_token(account["id"])},
        timeout=5,
    )
    entry = next(
        item
        for item in response.json()["items"]
        if item["contact_id"] == str(contact["id"])
    )
    assert {"kind": "access_role", "access_role_name": access_role["name"]} in entry[
        "roles"
    ]


def test_address_book_group_path_lists_ancestors_root_to_leaf(
    records, person, session_token, hierarchy
):
    root, child = hierarchy
    contact, account = person()
    records(
        "contact_roles_groups",
        contact_id=contact["id"],
        role_type_id=role_type_id("Group Leader"),
        group_id=child["id"],
        start_date=date.today(),
    )
    response = httpx.get(
        f"{API_URL}/api/v1/address-book",
        params={"page_size": 100},
        cookies={"crm_session": session_token(account["id"])},
        timeout=5,
    )
    entry = next(
        item
        for item in response.json()["items"]
        if item["contact_id"] == str(contact["id"])
    )
    assert entry["roles"][0]["group_path"] == [
        {"id": str(root["id"]), "name": root["name"]},
        {"id": str(child["id"]), "name": child["name"]},
    ]


# --- GET /api/v1/address-book/{contact_id} ----------------------------------


def test_address_book_detail_returns_matching_entry(records, person, session_token, group):
    contact, account = person()
    records(
        "contact_roles_groups",
        contact_id=contact["id"],
        role_type_id=role_type_id("Group Helper"),
        group_id=group["id"],
        start_date=date.today(),
    )
    response = httpx.get(
        f"{API_URL}/api/v1/address-book/{contact['id']}",
        cookies={"crm_session": session_token(account["id"])},
        timeout=5,
    )
    assert response.status_code == 200
    assert response.json()["contact_id"] == str(contact["id"])


def test_address_book_detail_returns_404_for_a_non_member(person, eligible_viewer):
    non_member, _ = person()
    response = httpx.get(
        f"{API_URL}/api/v1/address-book/{non_member['id']}",
        cookies={"crm_session": eligible_viewer},
        timeout=5,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Address book entry not found"}


def test_address_book_detail_returns_404_for_unknown_uuid(eligible_viewer):
    response = httpx.get(
        f"{API_URL}/api/v1/address-book/{uuid4()}",
        cookies={"crm_session": eligible_viewer},
        timeout=5,
    )
    assert response.status_code == 404


def test_address_book_detail_rejects_malformed_uuid(eligible_viewer):
    response = httpx.get(
        f"{API_URL}/api/v1/address-book/not-a-uuid",
        cookies={"crm_session": eligible_viewer},
        timeout=5,
    )
    assert response.status_code == 422


def test_address_book_detail_requires_eligibility_too(person, session_token):
    _, account = person()
    other, _ = person()
    response = httpx.get(
        f"{API_URL}/api/v1/address-book/{other['id']}",
        cookies={"crm_session": session_token(account["id"])},
        timeout=5,
    )
    assert response.status_code == 403


# --- GET/PATCH /api/v1/address-book/visibility ------------------------------


def test_directory_visibility_requires_a_session():
    with httpx.Client() as client:
        response = client.get(f"{API_URL}/api/v1/address-book/visibility", timeout=5)
    assert response.status_code == 401


def test_directory_visibility_available_without_an_eligible_role(person, session_token):
    _, account = person()
    response = httpx.get(
        f"{API_URL}/api/v1/address-book/visibility",
        cookies={"crm_session": session_token(account["id"])},
        timeout=5,
    )
    assert response.status_code == 200
    assert response.json() == {"hidden_from_directory": False, "roles": []}


def test_directory_visibility_lists_current_eligible_roles(
    records, person, session_token, group
):
    contact, account = person()
    records(
        "contact_roles_groups",
        contact_id=contact["id"],
        role_type_id=role_type_id("Group Leader"),
        group_id=group["id"],
        start_date=date.today(),
    )
    response = httpx.get(
        f"{API_URL}/api/v1/address-book/visibility",
        cookies={"crm_session": session_token(account["id"])},
        timeout=5,
    )
    body = response.json()
    assert body["hidden_from_directory"] is False
    assert len(body["roles"]) == 1
    assert body["roles"][0]["role_type_name"] == "Group Leader"
    assert body["roles"][0]["hidden_from_directory"] is False


def test_directory_visibility_patch_hides_the_whole_profile(
    records, person, session_token, group, caller
):
    contact, account = person()
    records(
        "contact_roles_groups",
        contact_id=contact["id"],
        role_type_id=role_type_id("Group Leader"),
        group_id=group["id"],
        start_date=date.today(),
    )
    caller.cookies.set("crm_session", session_token(account["id"]))
    before = tag(caller, "/api/v1/address-book/visibility")
    response = caller.patch(
        "/api/v1/address-book/visibility",
        headers={"If-Match": before},
        json={"hidden_from_directory": True},
    )
    assert response.status_code == 200
    assert response.json()["hidden_from_directory"] is True

    viewer, viewer_account = person()
    records(
        "contact_roles_groups",
        contact_id=viewer["id"],
        role_type_id=role_type_id("Area Manager"),
        group_id=group["id"],
        start_date=date.today(),
    )
    listing = httpx.get(
        f"{API_URL}/api/v1/address-book",
        params={"page_size": 100},
        cookies={"crm_session": session_token(viewer_account["id"])},
        timeout=5,
    )
    assert str(contact["id"]) not in {
        item["contact_id"] for item in listing.json()["items"]
    }


def test_directory_visibility_patch_hides_a_specific_role(
    records, person, session_token, group, caller
):
    contact, account = person()
    leader_role = records(
        "contact_roles_groups",
        contact_id=contact["id"],
        role_type_id=role_type_id("Group Leader"),
        group_id=group["id"],
        start_date=date.today(),
    )
    records(
        "contact_roles_groups",
        contact_id=contact["id"],
        role_type_id=role_type_id("Group Helper"),
        group_id=group["id"],
        start_date=date(2000, 1, 1),
    )
    caller.cookies.set("crm_session", session_token(account["id"]))
    before = tag(caller, "/api/v1/address-book/visibility")
    response = caller.patch(
        "/api/v1/address-book/visibility",
        headers={"If-Match": before},
        json={"roles": [{"id": str(leader_role["id"]), "hidden_from_directory": True}]},
    )
    assert response.status_code == 200

    detail = httpx.get(
        f"{API_URL}/api/v1/address-book/{contact['id']}",
        cookies={"crm_session": session_token(account["id"])},
        timeout=5,
    )
    role_names = {role["role_type_name"] for role in detail.json()["roles"]}
    assert role_names == {"Group Helper"}


def test_directory_visibility_patch_rejects_a_foreign_role_id(
    records, person, session_token, group, caller
):
    _, account = person()
    other, _ = person()
    other_role = records(
        "contact_roles_groups",
        contact_id=other["id"],
        role_type_id=role_type_id("Group Leader"),
        group_id=group["id"],
        start_date=date.today(),
    )
    caller.cookies.set("crm_session", session_token(account["id"]))
    before = tag(caller, "/api/v1/address-book/visibility")
    response = caller.patch(
        "/api/v1/address-book/visibility",
        headers={"If-Match": before},
        json={"roles": [{"id": str(other_role["id"]), "hidden_from_directory": True}]},
    )
    assert response.status_code == 422


def test_directory_visibility_patch_rejects_an_ended_own_role_id(
    records, person, session_token, group, caller
):
    """A role id the caller owns but that is no longer a *current* eligible
    assignment (documents/api-contract.md) must be rejected the same way a
    foreign role id is, not silently accepted because ownership alone matched."""
    contact, account = person()
    ended_role = records(
        "contact_roles_groups",
        contact_id=contact["id"],
        role_type_id=role_type_id("Group Leader"),
        group_id=group["id"],
        start_date=date(2000, 1, 1),
        end_date=date(2000, 12, 31),
    )
    caller.cookies.set("crm_session", session_token(account["id"]))
    before = tag(caller, "/api/v1/address-book/visibility")
    response = caller.patch(
        "/api/v1/address-book/visibility",
        headers={"If-Match": before},
        json={"roles": [{"id": str(ended_role["id"]), "hidden_from_directory": True}]},
    )
    assert response.status_code == 422


def test_directory_visibility_patch_rejects_an_ineligible_own_role_type_id(
    records, person, session_token, group, caller
):
    """Owning the row isn't enough either: a role type outside the eligible
    set (Group Leader/Group Helper/Area Manager) is never a directory
    entry — PATCH must reject its id the same way GET already excludes it."""
    contact, account = person()
    other_role_type = records("role_types", name=f"Committee Member {uuid4()}")
    ineligible_role = records(
        "contact_roles_groups",
        contact_id=contact["id"],
        role_type_id=other_role_type["id"],
        group_id=group["id"],
        start_date=date.today(),
    )
    caller.cookies.set("crm_session", session_token(account["id"]))
    before = tag(caller, "/api/v1/address-book/visibility")
    response = caller.patch(
        "/api/v1/address-book/visibility",
        headers={"If-Match": before},
        json={"roles": [{"id": str(ineligible_role["id"]), "hidden_from_directory": True}]},
    )
    assert response.status_code == 422


def test_directory_visibility_patch_rejects_empty_body(person, session_token, caller):
    _, account = person()
    caller.cookies.set("crm_session", session_token(account["id"]))
    before = tag(caller, "/api/v1/address-book/visibility")
    response = caller.patch(
        "/api/v1/address-book/visibility", headers={"If-Match": before}, json={}
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "header,expected",
    [(None, 428), ("*", 422), ('W/"x"', 422), ('"stale"', 412)],
)
def test_directory_visibility_patch_requires_current_single_strong_tag(
    person, session_token, caller, header, expected
):
    _, account = person()
    caller.cookies.set("crm_session", session_token(account["id"]))
    response = caller.patch(
        "/api/v1/address-book/visibility",
        json={"hidden_from_directory": True},
        headers={} if header is None else {"If-Match": header},
    )
    assert response.status_code == expected


@pytest.mark.parametrize(
    "headers",
    [{"Origin": "https://evil.example"}, {"X-CRM-CSRF": "wrong"}],
)
def test_directory_visibility_patch_csrf_rejected(person, session_token, caller, headers):
    _, account = person()
    caller.cookies.set("crm_session", session_token(account["id"]))
    before = tag(caller, "/api/v1/address-book/visibility")
    response = caller.patch(
        "/api/v1/address-book/visibility",
        json={"hidden_from_directory": True},
        headers={"If-Match": before, **headers},
    )
    assert response.status_code == 403


def test_directory_visibility_patch_audits_the_change(person, session_token, caller):
    _, account = person()
    caller.cookies.set("crm_session", session_token(account["id"]))
    before = tag(caller, "/api/v1/address-book/visibility")
    caller.patch(
        "/api/v1/address-book/visibility",
        headers={"If-Match": before},
        json={"hidden_from_directory": True},
    )
    events = database_rows(
        "SELECT id FROM audit_events WHERE event_type = 'directory_visibility.updated' "
        "AND user_account_id = %s",
        (account["id"],),
    )
    assert len(events) == 1

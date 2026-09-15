"""Behavioral contract for personal-details fields on contacts.

See documents/api-contract.md "Personal details" and
documents/contact-data-expansion-design.md. These five fields
(date_of_birth, preferred_name, phonetic_name, pronouns, gender) live on
the same PATCH /api/v1/contacts/{id} endpoint as the existing core fields
(first_name, last_name, email, status), but are gated by a distinct
action, contact-personal:update, checked independently of contact:update.
CSRF/If-Match mechanics reuse the same shared dependencies
test_contact_writes.py already exercises exhaustively; this file focuses
on what's new: the self/Main-Contact/Group-Leader write-access model for
these fields, and the mixed-field-authorization behavior of one endpoint
serving two permission levels.
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest

from .support import API_URL, database_rows


pytestmark = pytest.mark.contract


def role_type_id(name):
    return database_rows("SELECT id FROM role_types WHERE name = %s", (name,))[0]["id"]


@pytest.fixture
def admin_writer(callback_client):
    import os

    client, _ = callback_client
    client.cookies.set("crm_session", os.environ["AUTH_TEST_SESSION_TOKEN"])
    client.headers.update({"Origin": "http://localhost:5173", "X-CRM-CSRF": "1"})
    return client


@pytest.fixture
def actor_writer(callback_client, session_token):
    """A routed client authenticated as an arbitrary account, with write headers set."""

    def become(account_id):
        client, _ = callback_client
        client.cookies.set("crm_session", session_token(account_id))
        client.headers.update({"Origin": "http://localhost:5173", "X-CRM-CSRF": "1"})
        return client

    return become


def tag(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers.get("etag"), "Detail GET must expose an ETag"
    return response.headers["etag"]


@pytest.fixture
def family_of(records, person):
    """Build {target, main_contact_account, outsider_account} around a fresh
    contact belonging to a family unit with a current Main Contact."""

    def build():
        family = records("family_units", id=uuid4())
        target, target_account = person()
        records(
            "contact_family_units",
            contact_id=target["id"],
            family_unit_id=family["id"],
            relationship="child",
        )
        main_contact, main_contact_account = person()
        records(
            "contact_family_units",
            contact_id=main_contact["id"],
            family_unit_id=family["id"],
            relationship="parent",
        )
        records(
            "contact_family_main_contacts",
            family_unit_id=family["id"],
            contact_id=main_contact["id"],
        )
        outsider, outsider_account = person()
        return {
            "target": target,
            "target_account": target_account,
            "main_contact_account": main_contact_account,
            "outsider_account": outsider_account,
        }

    return build


@pytest.fixture
def group_leader_over(records, person):
    """Build a group with a Group Leader and one member, whose parent is a
    separate contact in the member's own family unit. Returns the leader's
    account, the member contact, and the member's parent contact."""

    def build():
        group_type = records("group_types", name=f"Personal details group type {uuid4()}")
        group = records(
            "groups", group_type_id=group_type["id"], name=f"Personal details group {uuid4()}"
        )
        leader, leader_account = person()
        records(
            "contact_roles_groups",
            contact_id=leader["id"],
            role_type_id=role_type_id("Group Leader"),
            group_id=group["id"],
            start_date=date.today(),
        )
        member, _ = person()
        records(
            "contact_roles_groups",
            contact_id=member["id"],
            role_type_id=role_type_id("Group Helper"),
            group_id=group["id"],
            start_date=date.today(),
        )
        family = records("family_units", id=uuid4())
        records(
            "contact_family_units", contact_id=member["id"], family_unit_id=family["id"], relationship="child"
        )
        parent, _ = person()
        records(
            "contact_family_units", contact_id=parent["id"], family_unit_id=family["id"], relationship="parent"
        )
        return {"leader_account": leader_account, "member": member, "parent": parent}

    return build


def test_contact_response_includes_personal_detail_fields(person):
    contact, _ = person()

    import httpx

    response = httpx.get(f"{API_URL}/api/v1/contacts/{contact['id']}", timeout=5)

    assert response.status_code == 200
    body = response.json()
    for field in ("date_of_birth", "preferred_name", "phonetic_name", "pronouns", "gender"):
        assert field in body
        assert body[field] is None


def test_self_can_update_own_personal_details(person, actor_writer):
    contact, account = person()
    client = actor_writer(account["id"])
    location = f"/api/v1/contacts/{contact['id']}"

    response = client.patch(
        location,
        json={"preferred_name": "Robbie", "pronouns": "they/them"},
        headers={"If-Match": tag(client, location)},
    )
    assert response.status_code == 200
    assert response.json()["preferred_name"] == "Robbie"
    assert response.json()["pronouns"] == "they/them"


def test_self_cannot_update_own_core_fields(person, actor_writer):
    contact, account = person()
    client = actor_writer(account["id"])
    location = f"/api/v1/contacts/{contact['id']}"

    response = client.patch(
        location,
        json={"first_name": "Changed"},
        headers={"If-Match": tag(client, location)},
    )
    assert response.status_code == 403


def test_main_contact_can_update_a_family_members_personal_details(family_of, actor_writer):
    people = family_of()
    client = actor_writer(people["main_contact_account"]["id"])
    location = f"/api/v1/contacts/{people['target']['id']}"

    response = client.patch(
        location,
        json={"gender": "non-binary"},
        headers={"If-Match": tag(client, location)},
    )
    assert response.status_code == 200
    assert response.json()["gender"] == "non-binary"


def test_group_leader_can_update_a_group_members_family_personal_details(group_leader_over, actor_writer):
    setup = group_leader_over()
    client = actor_writer(setup["leader_account"]["id"])
    location = f"/api/v1/contacts/{setup['parent']['id']}"

    response = client.patch(
        location,
        json={"phonetic_name": "PAIR-ent"},
        headers={"If-Match": tag(client, location)},
    )
    assert response.status_code == 200
    assert response.json()["phonetic_name"] == "PAIR-ent"


def test_outsider_cannot_update_personal_details(family_of, actor_writer):
    people = family_of()
    client = actor_writer(people["outsider_account"]["id"])
    location = f"/api/v1/contacts/{people['target']['id']}"

    # The outsider has no contact:view scope over the target either, so a
    # real ETag isn't obtainable here - matches the placeholder-If-Match
    # pattern test_contact_writes.py already uses for this same reason:
    # authorization is checked before If-Match validation.
    response = client.patch(
        location,
        json={"pronouns": "she/her"},
        headers={"If-Match": '"placeholder"'},
    )
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["Area Manager", "Group Helper"])
def test_area_manager_and_group_helper_cannot_update_personal_details(records, person, actor_writer, role):
    group_type = records("group_types", name=f"Personal details no-write type {uuid4()}")
    group = records("groups", group_type_id=group_type["id"], name=f"Personal details no-write {uuid4()}")
    holder, holder_account = person()
    records(
        "contact_roles_groups",
        contact_id=holder["id"],
        role_type_id=role_type_id(role),
        group_id=group["id"],
        start_date=date.today(),
    )
    member, _ = person()
    records(
        "contact_roles_groups",
        contact_id=member["id"],
        role_type_id=role_type_id("Group Helper"),
        group_id=group["id"],
        start_date=date.today(),
    )

    client = actor_writer(holder_account["id"])
    location = f"/api/v1/contacts/{member['id']}"
    response = client.patch(
        location,
        json={"pronouns": "she/her"},
        headers={"If-Match": '"placeholder"'},
    )
    assert response.status_code == 403


def test_mixing_core_and_personal_fields_requires_both_permissions(person, actor_writer):
    contact, account = person()
    client = actor_writer(account["id"])
    location = f"/api/v1/contacts/{contact['id']}"

    response = client.patch(
        location,
        json={"preferred_name": "Robbie", "first_name": "Changed"},
        headers={"If-Match": tag(client, location)},
    )
    assert response.status_code == 403

    unchanged = client.get(location)
    assert unchanged.json()["preferred_name"] is None
    assert unchanged.json()["first_name"] == contact["first_name"]


def test_group_leader_can_update_both_kinds_of_field_in_one_request(group_leader_over, actor_writer):
    setup = group_leader_over()
    client = actor_writer(setup["leader_account"]["id"])
    location = f"/api/v1/contacts/{setup['member']['id']}"

    response = client.patch(
        location,
        json={"first_name": "Changed", "preferred_name": "Robbie"},
        headers={"If-Match": tag(client, location)},
    )
    assert response.status_code == 200
    assert response.json()["first_name"] == "Changed"
    assert response.json()["preferred_name"] == "Robbie"


def test_setting_date_of_birth_in_the_future_is_rejected(person, admin_writer):
    contact, _ = person()
    location = f"/api/v1/contacts/{contact['id']}"
    future = str(date.today() + timedelta(days=1))

    response = admin_writer.patch(
        location,
        json={"date_of_birth": future},
        headers={"If-Match": tag(admin_writer, location)},
    )
    assert response.status_code == 422


def test_personal_detail_fields_can_be_explicitly_nulled(person, admin_writer):
    contact, _ = person()
    location = f"/api/v1/contacts/{contact['id']}"

    first = admin_writer.patch(
        location,
        json={"preferred_name": "Robbie"},
        headers={"If-Match": tag(admin_writer, location)},
    )
    assert first.json()["preferred_name"] == "Robbie"

    second = admin_writer.patch(
        location,
        json={"preferred_name": None},
        headers={"If-Match": tag(admin_writer, location)},
    )
    assert second.status_code == 200
    assert second.json()["preferred_name"] is None


def test_personal_detail_write_requires_csrf(person, admin_writer):
    contact, _ = person()
    location = f"/api/v1/contacts/{contact['id']}"
    etag = tag(admin_writer, location)
    del admin_writer.headers["X-CRM-CSRF"]

    response = admin_writer.patch(
        location, json={"pronouns": "she/her"}, headers={"If-Match": etag}
    )
    assert response.status_code == 403


def test_personal_detail_write_audits_the_change(person, admin_writer):
    contact, _ = person()
    location = f"/api/v1/contacts/{contact['id']}"

    response = admin_writer.patch(
        location,
        json={"preferred_name": "Robbie"},
        headers={"If-Match": tag(admin_writer, location)},
    )
    assert response.status_code == 200

    events = database_rows(
        "SELECT * FROM audit_events WHERE event_type = 'contact.updated' "
        "AND details->>'contact_id' = %s AND details->'fields' ? 'preferred_name'",
        (str(contact["id"]),),
    )
    assert len(events) == 1

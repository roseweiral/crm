"""Behavioral contract for contact emergency contacts.

See documents/api-contract.md "Emergency contact" and
documents/contact-data-expansion-design.md. CSRF/If-Match mechanics reuse
the same shared dependencies test_contact_writes.py already exercises
exhaustively; this file spot-checks each once and focuses on what's new
here: reading requires contact:view-sensitive (not contact:view), writing
uses the same self/Main-Contact/Group-Leader-family model as phone numbers
and addresses, and removal is a genuine hard DELETE.
"""

import os
from datetime import date
from uuid import uuid4

import httpx
import pytest

from .support import API_URL, database_rows


pytestmark = pytest.mark.contract


def role_type_id(name):
    return database_rows("SELECT id FROM role_types WHERE name = %s", (name,))[0]["id"]


@pytest.fixture
def admin_writer(callback_client):
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


def payload(contact_id, emergency_contact_id, **values):
    return {
        "contact_id": str(contact_id),
        "emergency_contact_id": str(emergency_contact_id),
        "priority": 1,
        "relationship": "Mother",
        **values,
    }


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
    def build():
        group_type = records("group_types", name=f"Emergency contact group type {uuid4()}")
        group = records(
            "groups", group_type_id=group_type["id"], name=f"Emergency contact group {uuid4()}"
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


# --- Creation and write-access model -----------------------------------------


def test_create_requires_a_session(person):
    contact, _ = person()
    other, _ = person()
    with httpx.Client() as client:
        response = client.post(
            f"{API_URL}/api/v1/contact-emergency-contacts",
            json=payload(contact["id"], other["id"]),
            timeout=5,
        )
    assert response.status_code == 401


def test_self_can_create_and_edit_own_emergency_contact(records, person, actor_writer):
    contact, account = person()
    other, _ = person()
    client = actor_writer(account["id"])

    created = client.post(
        "/api/v1/contact-emergency-contacts", json=payload(contact["id"], other["id"])
    )
    assert created.status_code == 201
    assert created.json()["relationship"] == "Mother"
    records.track("contact_emergency_contacts", created.json()["id"])

    location = created.headers["location"]
    updated = client.patch(
        location, json={"relationship": "Neighbour"}, headers={"If-Match": tag(client, location)}
    )
    assert updated.status_code == 200
    assert updated.json()["relationship"] == "Neighbour"


def test_main_contact_can_write_a_family_members_emergency_contact(records, family_of, actor_writer, person):
    people = family_of()
    other, _ = person()
    client = actor_writer(people["main_contact_account"]["id"])

    response = client.post(
        "/api/v1/contact-emergency-contacts", json=payload(people["target"]["id"], other["id"])
    )
    assert response.status_code == 201
    records.track("contact_emergency_contacts", response.json()["id"])


def test_group_leader_can_write_a_group_members_family_emergency_contact(records, group_leader_over, actor_writer, person):
    setup = group_leader_over()
    other, _ = person()
    client = actor_writer(setup["leader_account"]["id"])

    response = client.post(
        "/api/v1/contact-emergency-contacts", json=payload(setup["parent"]["id"], other["id"])
    )
    assert response.status_code == 201
    records.track("contact_emergency_contacts", response.json()["id"])


def test_outsider_cannot_write_another_contacts_emergency_contact(records, family_of, actor_writer, person):
    people = family_of()
    other, _ = person()
    client = actor_writer(people["outsider_account"]["id"])

    response = client.post(
        "/api/v1/contact-emergency-contacts", json=payload(people["target"]["id"], other["id"])
    )
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["Area Manager", "Group Helper"])
def test_area_manager_and_group_helper_cannot_write_emergency_contacts(records, person, actor_writer, role):
    group_type = records("group_types", name=f"Emergency contact no-write type {uuid4()}")
    group = records("groups", group_type_id=group_type["id"], name=f"Emergency contact no-write {uuid4()}")
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
    other, _ = person()

    client = actor_writer(holder_account["id"])
    response = client.post(
        "/api/v1/contact-emergency-contacts", json=payload(member["id"], other["id"])
    )
    assert response.status_code == 403


# --- Validation and conflicts -------------------------------------------------


def test_cannot_set_yourself_as_your_own_emergency_contact(person, admin_writer):
    contact, _ = person()
    response = admin_writer.post(
        "/api/v1/contact-emergency-contacts", json=payload(contact["id"], contact["id"])
    )
    assert response.status_code == 422


def test_emergency_contact_id_must_reference_an_existing_contact(person, admin_writer):
    contact, _ = person()
    response = admin_writer.post(
        "/api/v1/contact-emergency-contacts",
        json=payload(contact["id"], "00000000-0000-0000-0000-000000000000"),
    )
    assert response.status_code == 422


def test_duplicate_priority_for_the_same_contact_conflicts(records, person, admin_writer):
    contact, _ = person()
    first_other, _ = person()
    second_other, _ = person()

    first = admin_writer.post(
        "/api/v1/contact-emergency-contacts", json=payload(contact["id"], first_other["id"], priority=1)
    )
    assert first.status_code == 201
    records.track("contact_emergency_contacts", first.json()["id"])

    second = admin_writer.post(
        "/api/v1/contact-emergency-contacts", json=payload(contact["id"], second_other["id"], priority=1)
    )
    assert second.status_code == 409


def test_duplicate_emergency_contact_for_the_same_contact_conflicts(records, person, admin_writer):
    contact, _ = person()
    other, _ = person()

    first = admin_writer.post(
        "/api/v1/contact-emergency-contacts", json=payload(contact["id"], other["id"], priority=1)
    )
    assert first.status_code == 201
    records.track("contact_emergency_contacts", first.json()["id"])

    second = admin_writer.post(
        "/api/v1/contact-emergency-contacts", json=payload(contact["id"], other["id"], priority=2)
    )
    assert second.status_code == 409


# --- Reading: contact:view-sensitive, not contact:view -----------------------


def test_emergency_contact_detail_conceals_existence_outside_scope(records, family_of, actor_writer, person):
    people = family_of()
    other, _ = person()
    created = actor_writer(people["main_contact_account"]["id"]).post(
        "/api/v1/contact-emergency-contacts", json=payload(people["target"]["id"], other["id"])
    )
    records.track("contact_emergency_contacts", created.json()["id"])
    location = created.headers["location"]

    outsider_client = actor_writer(people["outsider_account"]["id"])
    response = outsider_client.get(location)
    assert response.status_code == 404


def test_self_can_read_own_emergency_contact(records, person, actor_writer):
    contact, account = person()
    other, _ = person()
    client = actor_writer(account["id"])
    created = client.post("/api/v1/contact-emergency-contacts", json=payload(contact["id"], other["id"]))
    records.track("contact_emergency_contacts", created.json()["id"])

    response = client.get(created.headers["location"])
    assert response.status_code == 200


def test_emergency_contact_list_filters_by_contact_id(records, person, admin_writer):
    contact_a, _ = person()
    contact_b, _ = person()
    other_a, _ = person()
    other_b, _ = person()
    created_a = admin_writer.post(
        "/api/v1/contact-emergency-contacts", json=payload(contact_a["id"], other_a["id"])
    )
    created_b = admin_writer.post(
        "/api/v1/contact-emergency-contacts", json=payload(contact_b["id"], other_b["id"])
    )
    records.track("contact_emergency_contacts", created_a.json()["id"])
    records.track("contact_emergency_contacts", created_b.json()["id"])

    response = admin_writer.get(
        "/api/v1/contact-emergency-contacts", params={"contact_id": str(contact_a["id"])}
    )
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert created_a.json()["id"] in ids
    assert created_b.json()["id"] not in ids


# --- Deletion (the one hard delete in this system) ----------------------------


def test_deleting_an_emergency_contact_removes_the_row(records, person, admin_writer):
    contact, _ = person()
    other, _ = person()
    created = admin_writer.post("/api/v1/contact-emergency-contacts", json=payload(contact["id"], other["id"]))
    location = created.headers["location"]

    response = admin_writer.delete(location, headers={"If-Match": tag(admin_writer, location)})
    assert response.status_code == 204

    rows = database_rows(
        "SELECT id FROM contact_emergency_contacts WHERE id = %s", (created.json()["id"],)
    )
    assert rows == []


def test_delete_requires_csrf(records, person, admin_writer):
    contact, _ = person()
    other, _ = person()
    created = admin_writer.post("/api/v1/contact-emergency-contacts", json=payload(contact["id"], other["id"]))
    records.track("contact_emergency_contacts", created.json()["id"])
    location = created.headers["location"]
    etag = tag(admin_writer, location)
    del admin_writer.headers["X-CRM-CSRF"]

    response = admin_writer.delete(location, headers={"If-Match": etag})
    assert response.status_code == 403


def test_delete_requires_if_match(records, person, admin_writer):
    contact, _ = person()
    other, _ = person()
    created = admin_writer.post("/api/v1/contact-emergency-contacts", json=payload(contact["id"], other["id"]))
    records.track("contact_emergency_contacts", created.json()["id"])
    location = created.headers["location"]

    response = admin_writer.delete(location)
    assert response.status_code == 428


def test_outsider_cannot_delete_another_contacts_emergency_contact(records, family_of, actor_writer, person):
    people = family_of()
    other, _ = person()
    created = actor_writer(people["main_contact_account"]["id"]).post(
        "/api/v1/contact-emergency-contacts", json=payload(people["target"]["id"], other["id"])
    )
    records.track("contact_emergency_contacts", created.json()["id"])
    location = created.headers["location"]

    outsider_client = actor_writer(people["outsider_account"]["id"])
    response = outsider_client.delete(location, headers={"If-Match": '"placeholder"'})
    assert response.status_code == 403

    rows = database_rows(
        "SELECT id FROM contact_emergency_contacts WHERE id = %s", (created.json()["id"],)
    )
    assert len(rows) == 1


# --- Shared conventions -------------------------------------------------------


def test_write_requires_csrf(records, person, admin_writer):
    contact, _ = person()
    other, _ = person()
    del admin_writer.headers["X-CRM-CSRF"]
    response = admin_writer.post(
        "/api/v1/contact-emergency-contacts", json=payload(contact["id"], other["id"])
    )
    assert response.status_code == 403


def test_create_audits_the_change(records, person, admin_writer):
    contact, _ = person()
    other, _ = person()
    created = admin_writer.post(
        "/api/v1/contact-emergency-contacts", json=payload(contact["id"], other["id"])
    )
    records.track("contact_emergency_contacts", created.json()["id"])

    events = database_rows(
        "SELECT * FROM audit_events WHERE event_type = 'contact_emergency_contact.created' "
        "AND details->>'contact_emergency_contact_id' = %s",
        (created.json()["id"],),
    )
    assert len(events) == 1


def test_delete_audits_the_change(records, person, admin_writer):
    contact, _ = person()
    other, _ = person()
    created = admin_writer.post(
        "/api/v1/contact-emergency-contacts", json=payload(contact["id"], other["id"])
    )
    location = created.headers["location"]

    admin_writer.delete(location, headers={"If-Match": tag(admin_writer, location)})

    events = database_rows(
        "SELECT * FROM audit_events WHERE event_type = 'contact_emergency_contact.deleted' "
        "AND details->>'contact_emergency_contact_id' = %s",
        (created.json()["id"],),
    )
    assert len(events) == 1

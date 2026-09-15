"""Behavioral contract for contact phone numbers and addresses.

See documents/api-contract.md "Contact details: phone numbers and
addresses" and documents/contact-data-expansion-design.md. CSRF/If-Match
mechanics reuse the same shared dependencies test_contact_writes.py
already exercises exhaustively; this file spot-checks each once rather
than repeating that matrix, and focuses on what's new here: the
self/Main-Contact/Group-Leader-family write-access model and the
is_primary transition.
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


def phone_payload(contact_id, **values):
    return {"contact_id": str(contact_id), "phone_type": "mobile", "number": "07700 900000", **values}


def address_payload(contact_id, **values):
    return {"contact_id": str(contact_id), "line1": "1 Example Street", **values}


@pytest.fixture
def family_of(records, person):
    """Build {self, main_contact_viewer, group_leader_viewer, outsider} around a
    fresh contact, each set up for a distinct write-access-model actor."""

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


# --- Phone numbers -----------------------------------------------------------


def test_phone_number_create_requires_a_session(person):
    contact, _ = person()
    with httpx.Client() as client:
        response = client.post(
            f"{API_URL}/api/v1/contact-phone-numbers",
            json=phone_payload(contact["id"]),
            timeout=5,
        )
    assert response.status_code == 401


def test_self_can_create_and_edit_own_phone_number(records, person, actor_writer):
    contact, account = person()
    client = actor_writer(account["id"])

    created = client.post("/api/v1/contact-phone-numbers", json=phone_payload(contact["id"]))
    assert created.status_code == 201
    assert created.json()["contact_id"] == str(contact["id"])
    assert created.json()["is_primary"] is False
    records.track("contact_phone_numbers", created.json()["id"])

    location = created.headers["location"]
    updated = client.patch(
        location, json={"number": "07700 900111"}, headers={"If-Match": tag(client, location)}
    )
    assert updated.status_code == 200
    assert updated.json()["number"] == "07700 900111"


def test_main_contact_can_write_a_family_members_phone_number(records, family_of, actor_writer):
    people = family_of()
    client = actor_writer(people["main_contact_account"]["id"])

    response = client.post("/api/v1/contact-phone-numbers", json=phone_payload(people["target"]["id"]))
    assert response.status_code == 201
    records.track("contact_phone_numbers", response.json()["id"])


def test_group_leader_can_write_a_group_members_family_phone_number(
    records, person, actor_writer
):
    group_type = records("group_types", name=f"Contact details group type {uuid4()}")
    group = records("groups", group_type_id=group_type["id"], name=f"Contact details group {uuid4()}")
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
    records("contact_family_units", contact_id=member["id"], family_unit_id=family["id"], relationship="child")
    parent, _ = person()
    records("contact_family_units", contact_id=parent["id"], family_unit_id=family["id"], relationship="parent")

    client = actor_writer(leader_account["id"])
    response = client.post("/api/v1/contact-phone-numbers", json=phone_payload(parent["id"]))
    assert response.status_code == 201
    records.track("contact_phone_numbers", response.json()["id"])


def test_outsider_cannot_write_another_contacts_phone_number(records, family_of, actor_writer):
    people = family_of()
    client = actor_writer(people["outsider_account"]["id"])

    response = client.post("/api/v1/contact-phone-numbers", json=phone_payload(people["target"]["id"]))
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["Area Manager", "Group Helper"])
def test_area_manager_and_group_helper_cannot_write_phone_numbers(
    records, person, actor_writer, role
):
    group_type = records("group_types", name=f"Contact details no-write type {uuid4()}")
    group = records("groups", group_type_id=group_type["id"], name=f"Contact details no-write {uuid4()}")
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
    response = client.post("/api/v1/contact-phone-numbers", json=phone_payload(member["id"]))
    assert response.status_code == 403


def test_setting_is_primary_unsets_the_previous_primary_atomically(records, person, admin_writer):
    contact, _ = person()
    first = admin_writer.post(
        "/api/v1/contact-phone-numbers", json=phone_payload(contact["id"], is_primary=True)
    )
    assert first.status_code == 201
    records.track("contact_phone_numbers", first.json()["id"])

    second = admin_writer.post(
        "/api/v1/contact-phone-numbers",
        json=phone_payload(contact["id"], number="07700 900222", is_primary=True),
    )
    assert second.status_code == 201
    records.track("contact_phone_numbers", second.json()["id"])

    rows = database_rows(
        "SELECT id, is_primary FROM contact_phone_numbers WHERE contact_id = %s AND end_date IS NULL",
        (contact["id"],),
    )
    primaries = [row for row in rows if row["is_primary"]]
    assert len(primaries) == 1
    assert str(primaries[0]["id"]) == second.json()["id"]


def test_ending_a_phone_number_is_how_its_removed(records, person, admin_writer):
    contact, _ = person()
    created = admin_writer.post("/api/v1/contact-phone-numbers", json=phone_payload(contact["id"]))
    records.track("contact_phone_numbers", created.json()["id"])
    location = created.headers["location"]

    response = admin_writer.patch(
        location,
        json={"end_date": str(date.today())},
        headers={"If-Match": tag(admin_writer, location)},
    )
    assert response.status_code == 200
    assert response.json()["end_date"] == str(date.today())


def test_phone_number_list_filters_by_contact_id(records, person, admin_writer):
    contact_a, _ = person()
    contact_b, _ = person()
    created_a = admin_writer.post("/api/v1/contact-phone-numbers", json=phone_payload(contact_a["id"]))
    created_b = admin_writer.post("/api/v1/contact-phone-numbers", json=phone_payload(contact_b["id"]))
    records.track("contact_phone_numbers", created_a.json()["id"])
    records.track("contact_phone_numbers", created_b.json()["id"])

    response = admin_writer.get(
        "/api/v1/contact-phone-numbers", params={"contact_id": str(contact_a["id"])}
    )
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert created_a.json()["id"] in ids
    assert created_b.json()["id"] not in ids


def test_phone_number_detail_returns_404_for_out_of_scope(records, family_of, actor_writer):
    people = family_of()
    created = actor_writer(people["main_contact_account"]["id"]).post(
        "/api/v1/contact-phone-numbers", json=phone_payload(people["target"]["id"])
    )
    records.track("contact_phone_numbers", created.json()["id"])
    location = created.headers["location"]

    outsider_client = actor_writer(people["outsider_account"]["id"])
    response = outsider_client.get(location)
    assert response.status_code == 404


def test_phone_number_write_requires_csrf(records, person, admin_writer):
    contact, _ = person()
    del admin_writer.headers["X-CRM-CSRF"]
    response = admin_writer.post("/api/v1/contact-phone-numbers", json=phone_payload(contact["id"]))
    assert response.status_code == 403


def test_phone_number_write_audits_the_change(records, person, admin_writer):
    contact, _ = person()
    created = admin_writer.post("/api/v1/contact-phone-numbers", json=phone_payload(contact["id"]))
    records.track("contact_phone_numbers", created.json()["id"])

    events = database_rows(
        "SELECT * FROM audit_events WHERE event_type = 'contact_phone_number.created' "
        "AND details->>'contact_phone_number_id' = %s",
        (created.json()["id"],),
    )
    assert len(events) == 1


# --- Addresses -----------------------------------------------------------


def test_address_create_defaults_to_home_type(records, person, admin_writer):
    contact, _ = person()
    response = admin_writer.post("/api/v1/contact-addresses", json=address_payload(contact["id"]))
    assert response.status_code == 201
    assert response.json()["address_type"] == "home"
    records.track("contact_addresses", response.json()["id"])


def test_self_can_create_own_address(records, person, actor_writer):
    contact, account = person()
    client = actor_writer(account["id"])
    response = client.post("/api/v1/contact-addresses", json=address_payload(contact["id"]))
    assert response.status_code == 201
    records.track("contact_addresses", response.json()["id"])


def test_outsider_cannot_write_another_contacts_address(records, family_of, actor_writer):
    people = family_of()
    client = actor_writer(people["outsider_account"]["id"])
    response = client.post("/api/v1/contact-addresses", json=address_payload(people["target"]["id"]))
    assert response.status_code == 403


def test_ending_an_address_is_how_its_removed(records, person, admin_writer):
    contact, _ = person()
    created = admin_writer.post("/api/v1/contact-addresses", json=address_payload(contact["id"]))
    records.track("contact_addresses", created.json()["id"])
    location = created.headers["location"]

    response = admin_writer.patch(
        location,
        json={"end_date": str(date.today())},
        headers={"If-Match": tag(admin_writer, location)},
    )
    assert response.status_code == 200
    assert response.json()["end_date"] == str(date.today())

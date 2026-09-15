"""Behavioral contract for the read-only contact profile aggregate.

See documents/api-contract.md "Contact profile (read-only aggregate)".
Authorization boundaries (contact:view, contact:view-sensitive) are
already exercised exhaustively by test_contacts_endpoints.py,
test_contact_details_endpoints.py, and test_contact_emergency_contacts.py;
this file focuses on what's new here: bundling everything into one
response, current-only filtering, and the emergency_contacts null-vs-empty
distinction.
"""

import os
from datetime import date
from uuid import uuid4

import httpx
import pytest

from .support import API_URL, database_rows


pytestmark = pytest.mark.contract


@pytest.fixture
def admin_writer(callback_client):
    client, _ = callback_client
    client.cookies.set("crm_session", os.environ["AUTH_TEST_SESSION_TOKEN"])
    client.headers.update({"Origin": "http://localhost:5173", "X-CRM-CSRF": "1"})
    return client


@pytest.fixture
def actor_writer(callback_client, session_token):
    def become(account_id):
        client, _ = callback_client
        client.cookies.set("crm_session", session_token(account_id))
        client.headers.update({"Origin": "http://localhost:5173", "X-CRM-CSRF": "1"})
        return client

    return become


def test_profile_requires_a_session(person):
    contact, _ = person()
    with httpx.Client() as client:
        response = client.get(
            f"{API_URL}/api/v1/contacts/{contact['id']}/profile", timeout=5
        )
    assert response.status_code == 401


def test_profile_returns_404_for_out_of_scope_contact(person, actor_writer):
    contact, _ = person()
    outsider, outsider_account = person()
    client = actor_writer(outsider_account["id"])

    response = client.get(f"/api/v1/contacts/{contact['id']}/profile")
    assert response.status_code == 404


def test_profile_returns_404_for_unknown_contact(admin_writer):
    response = admin_writer.get(f"/api/v1/contacts/{uuid4()}/profile")
    assert response.status_code == 404


def test_profile_includes_the_same_contact_fields_as_the_detail_endpoint(
    person, admin_writer
):
    contact, _ = person()

    detail = admin_writer.get(f"/api/v1/contacts/{contact['id']}")
    profile = admin_writer.get(f"/api/v1/contacts/{contact['id']}/profile")

    assert profile.status_code == 200
    assert profile.json()["contact"] == detail.json()


def test_profile_has_no_etag(person, admin_writer):
    contact, _ = person()
    response = admin_writer.get(f"/api/v1/contacts/{contact['id']}/profile")
    assert "etag" not in {key.lower() for key in response.headers}


def test_profile_includes_only_current_phone_numbers_and_addresses(
    records, person, admin_writer
):
    contact, _ = person()

    current_phone = admin_writer.post(
        "/api/v1/contact-phone-numbers",
        json={"contact_id": str(contact["id"]), "phone_type": "mobile", "number": "07700 900000"},
    ).json()
    records.track("contact_phone_numbers", current_phone["id"])

    ended_phone = admin_writer.post(
        "/api/v1/contact-phone-numbers",
        json={"contact_id": str(contact["id"]), "phone_type": "home", "number": "020 7946 0000"},
    ).json()
    records.track("contact_phone_numbers", ended_phone["id"])
    admin_writer.patch(
        f"/api/v1/contact-phone-numbers/{ended_phone['id']}",
        json={"end_date": str(date.today())},
        headers={"If-Match": admin_writer.get(f"/api/v1/contact-phone-numbers/{ended_phone['id']}").headers["etag"]},
    )

    current_address = admin_writer.post(
        "/api/v1/contact-addresses",
        json={"contact_id": str(contact["id"]), "line1": "1 Current Street"},
    ).json()
    records.track("contact_addresses", current_address["id"])

    ended_address = admin_writer.post(
        "/api/v1/contact-addresses",
        json={"contact_id": str(contact["id"]), "line1": "1 Old Street"},
    ).json()
    records.track("contact_addresses", ended_address["id"])
    admin_writer.patch(
        f"/api/v1/contact-addresses/{ended_address['id']}",
        json={"end_date": str(date.today())},
        headers={"If-Match": admin_writer.get(f"/api/v1/contact-addresses/{ended_address['id']}").headers["etag"]},
    )

    profile = admin_writer.get(f"/api/v1/contacts/{contact['id']}/profile").json()

    phone_ids = {item["id"] for item in profile["phone_numbers"]}
    address_ids = {item["id"] for item in profile["addresses"]}
    assert phone_ids == {current_phone["id"]}
    assert address_ids == {current_address["id"]}


def test_profile_emergency_contacts_reflects_current_entries(records, person, admin_writer):
    contact, _ = person()
    other, _ = person()

    created = admin_writer.post(
        "/api/v1/contact-emergency-contacts",
        json={
            "contact_id": str(contact["id"]),
            "emergency_contact_id": str(other["id"]),
            "priority": 1,
            "relationship": "Friend",
        },
    ).json()
    records.track("contact_emergency_contacts", created["id"])

    profile = admin_writer.get(f"/api/v1/contacts/{contact['id']}/profile").json()

    assert profile["emergency_contacts"] == [
        {
            "id": created["id"],
            "emergency_contact_id": str(other["id"]),
            "priority": 1,
            "relationship": "Friend",
            "first_name": other["first_name"],
            "last_name": other["last_name"],
            "email": other["email"],
            "phone_number": None,
        }
    ]


def test_profile_emergency_contacts_is_an_empty_list_not_null_when_none_recorded(
    person, admin_writer
):
    contact, _ = person()

    profile = admin_writer.get(f"/api/v1/contacts/{contact['id']}/profile").json()

    assert profile["emergency_contacts"] == []


def test_profile_emergency_contact_phone_number_prefers_the_current_primary(
    records, person, admin_writer
):
    contact, _ = person()
    other, _ = person()

    created = admin_writer.post(
        "/api/v1/contact-emergency-contacts",
        json={
            "contact_id": str(contact["id"]),
            "emergency_contact_id": str(other["id"]),
            "priority": 1,
            "relationship": "Friend",
        },
    ).json()
    records.track("contact_emergency_contacts", created["id"])

    secondary = admin_writer.post(
        "/api/v1/contact-phone-numbers",
        json={"contact_id": str(other["id"]), "phone_type": "home", "number": "020 7946 0001"},
    ).json()
    records.track("contact_phone_numbers", secondary["id"])
    primary = admin_writer.post(
        "/api/v1/contact-phone-numbers",
        json={
            "contact_id": str(other["id"]),
            "phone_type": "mobile",
            "number": "07700 900999",
            "is_primary": True,
        },
    ).json()
    records.track("contact_phone_numbers", primary["id"])

    profile = admin_writer.get(f"/api/v1/contacts/{contact['id']}/profile").json()

    assert profile["emergency_contacts"][0]["phone_number"] == "07700 900999"

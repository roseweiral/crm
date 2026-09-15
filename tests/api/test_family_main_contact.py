"""Behavioral contract for Main Contact tracking and reading.

See documents/api-contract.md "Main Contact tracking" for the full
contract and documents/contact-data-expansion-design.md for the rationale.
"""

import os
from uuid import uuid4

import httpx
import pytest

from .support import API_URL, database_rows


pytestmark = pytest.mark.contract


@pytest.fixture
def caller(callback_client):
    """A real routed client with the write-security headers already set."""
    client, _ = callback_client
    client.headers.update({"Origin": "http://localhost:5173", "X-CRM-CSRF": "1"})
    return client


@pytest.fixture
def admin_caller(caller):
    caller.cookies.set("crm_session", os.environ["AUTH_TEST_SESSION_TOKEN"])
    return caller


@pytest.fixture
def family(records, person):
    """A family unit with two eligible (non-child) members and one child."""
    family_unit = records("family_units", id=uuid4())

    parent_a, parent_a_account = person()
    records(
        "contact_family_units",
        contact_id=parent_a["id"],
        family_unit_id=family_unit["id"],
        relationship="parent",
    )
    parent_b, parent_b_account = person()
    records(
        "contact_family_units",
        contact_id=parent_b["id"],
        family_unit_id=family_unit["id"],
        relationship="guardian",
    )
    child, _ = person()
    records(
        "contact_family_units",
        contact_id=child["id"],
        family_unit_id=family_unit["id"],
        relationship="child",
    )
    return {
        "family_unit": family_unit,
        "parent_a": parent_a,
        "parent_a_account": parent_a_account,
        "parent_b": parent_b,
        "parent_b_account": parent_b_account,
        "child": child,
    }


def main_contact_ids(family_unit_id):
    rows = database_rows(
        "SELECT contact_id FROM contact_family_main_contacts "
        "WHERE family_unit_id = %s AND end_date IS NULL",
        (family_unit_id,),
    )
    return {row["contact_id"] for row in rows}


# --- GET exposes is_main_contact --------------------------------------------


def test_get_family_unit_shows_no_main_contact_by_default(family):
    family_unit_id = family["family_unit"]["id"]
    response = httpx.get(f"{API_URL}/api/v1/family-units/{family_unit_id}", timeout=5)
    assert response.status_code == 200
    assert all(member["is_main_contact"] is False for member in response.json()["members"])


def test_get_family_unit_shows_the_current_main_contact(family, admin_caller):
    family_unit_id = family["family_unit"]["id"]
    admin_caller.post(
        f"/api/v1/family-units/{family_unit_id}/main-contact",
        json={"contact_id": str(family["parent_a"]["id"])},
    )

    response = httpx.get(f"{API_URL}/api/v1/family-units/{family_unit_id}", timeout=5)
    assert response.status_code == 200
    flags = {member["contact_id"]: member["is_main_contact"] for member in response.json()["members"]}
    assert flags[str(family["parent_a"]["id"])] is True
    assert flags[str(family["parent_b"]["id"])] is False
    assert flags[str(family["child"]["id"])] is False


# --- POST .../main-contact ---------------------------------------------------


def test_set_main_contact_requires_a_session(family):
    family_unit_id = family["family_unit"]["id"]
    with httpx.Client() as client:
        response = client.post(
            f"{API_URL}/api/v1/family-units/{family_unit_id}/main-contact",
            json={"contact_id": str(family["parent_a"]["id"])},
            timeout=5,
        )
    assert response.status_code == 401


def test_set_main_contact_requires_global_admin(family, caller, person, session_token):
    _, account = person()
    caller.cookies.set("crm_session", session_token(account["id"]))
    family_unit_id = family["family_unit"]["id"]

    response = caller.post(
        f"/api/v1/family-units/{family_unit_id}/main-contact",
        json={"contact_id": str(family["parent_a"]["id"])},
    )
    assert response.status_code == 403


def test_set_main_contact_succeeds_and_ends_the_previous_holder(family, admin_caller):
    family_unit_id = family["family_unit"]["id"]

    first = admin_caller.post(
        f"/api/v1/family-units/{family_unit_id}/main-contact",
        json={"contact_id": str(family["parent_a"]["id"])},
    )
    assert first.status_code == 200
    assert main_contact_ids(family_unit_id) == {family["parent_a"]["id"]}

    second = admin_caller.post(
        f"/api/v1/family-units/{family_unit_id}/main-contact",
        json={"contact_id": str(family["parent_b"]["id"])},
    )
    assert second.status_code == 200
    body = second.json()
    flags = {member["contact_id"]: member["is_main_contact"] for member in body["members"]}
    assert flags[str(family["parent_b"]["id"])] is True
    assert flags[str(family["parent_a"]["id"])] is False
    assert main_contact_ids(family_unit_id) == {family["parent_b"]["id"]}

    ended = database_rows(
        "SELECT end_date FROM contact_family_main_contacts "
        "WHERE family_unit_id = %s AND contact_id = %s",
        (family_unit_id, family["parent_a"]["id"]),
    )
    assert ended[0]["end_date"] is not None


def test_set_main_contact_rejects_a_non_member(family, admin_caller, person):
    outsider, _ = person()
    family_unit_id = family["family_unit"]["id"]

    response = admin_caller.post(
        f"/api/v1/family-units/{family_unit_id}/main-contact",
        json={"contact_id": str(outsider["id"])},
    )
    assert response.status_code == 422


def test_set_main_contact_rejects_a_child_member(family, admin_caller):
    family_unit_id = family["family_unit"]["id"]

    response = admin_caller.post(
        f"/api/v1/family-units/{family_unit_id}/main-contact",
        json={"contact_id": str(family["child"]["id"])},
    )
    assert response.status_code == 422


def test_set_main_contact_rejects_an_unknown_family_unit(admin_caller, family):
    response = admin_caller.post(
        f"/api/v1/family-units/{uuid4()}/main-contact",
        json={"contact_id": str(family["parent_a"]["id"])},
    )
    assert response.status_code == 404


def test_set_main_contact_rejects_malformed_ids(admin_caller, family):
    family_unit_id = family["family_unit"]["id"]

    response = admin_caller.post(
        f"/api/v1/family-units/{family_unit_id}/main-contact",
        json={"contact_id": "not-a-uuid"},
    )
    assert response.status_code == 422

    response = admin_caller.post(
        "/api/v1/family-units/not-a-uuid/main-contact",
        json={"contact_id": str(family["parent_a"]["id"])},
    )
    assert response.status_code == 422


def test_set_main_contact_is_idempotent_for_the_current_holder(family, admin_caller):
    family_unit_id = family["family_unit"]["id"]
    admin_caller.post(
        f"/api/v1/family-units/{family_unit_id}/main-contact",
        json={"contact_id": str(family["parent_a"]["id"])},
    )
    before_rows = database_rows(
        "SELECT id FROM contact_family_main_contacts WHERE family_unit_id = %s",
        (family_unit_id,),
    )
    before_event_count = len(
        database_rows(
            "SELECT id FROM audit_events WHERE event_type = 'family.main_contact_changed' "
            "AND details->>'family_unit_id' = %s",
            (str(family_unit_id),),
        )
    )

    response = admin_caller.post(
        f"/api/v1/family-units/{family_unit_id}/main-contact",
        json={"contact_id": str(family["parent_a"]["id"])},
    )
    assert response.status_code == 200

    after_rows = database_rows(
        "SELECT id FROM contact_family_main_contacts WHERE family_unit_id = %s",
        (family_unit_id,),
    )
    assert before_rows == after_rows

    after_event_count = len(
        database_rows(
            "SELECT id FROM audit_events WHERE event_type = 'family.main_contact_changed' "
            "AND details->>'family_unit_id' = %s",
            (str(family_unit_id),),
        )
    )
    assert after_event_count == before_event_count


def test_set_main_contact_revokes_the_outgoing_holders_sessions(
    family, admin_caller, session_token
):
    family_unit_id = family["family_unit"]["id"]
    outgoing_token = session_token(family["parent_a_account"]["id"])
    admin_caller.post(
        f"/api/v1/family-units/{family_unit_id}/main-contact",
        json={"contact_id": str(family["parent_a"]["id"])},
    )

    admin_caller.post(
        f"/api/v1/family-units/{family_unit_id}/main-contact",
        json={"contact_id": str(family["parent_b"]["id"])},
    )

    response = httpx.get(
        f"{API_URL}/api/v1/me",
        cookies={"crm_session": outgoing_token},
        timeout=5,
    )
    assert response.status_code == 401


def test_set_main_contact_audits_the_change(family, admin_caller):
    family_unit_id = family["family_unit"]["id"]
    admin_caller.post(
        f"/api/v1/family-units/{family_unit_id}/main-contact",
        json={"contact_id": str(family["parent_a"]["id"])},
    )

    events = database_rows(
        "SELECT details FROM audit_events WHERE event_type = 'family.main_contact_changed' "
        "AND details->>'family_unit_id' = %s",
        (str(family_unit_id),),
    )
    assert len(events) == 1
    assert events[0]["details"]["incoming_contact_id"] == str(family["parent_a"]["id"])
    assert events[0]["details"]["outgoing_contact_id"] is None


def test_set_main_contact_rejects_bad_origin(family, caller):
    caller.cookies.set("crm_session", os.environ["AUTH_TEST_SESSION_TOKEN"])
    caller.headers.update({"Origin": "https://evil.example"})
    family_unit_id = family["family_unit"]["id"]

    response = caller.post(
        f"/api/v1/family-units/{family_unit_id}/main-contact",
        json={"contact_id": str(family["parent_a"]["id"])},
    )
    assert response.status_code == 403


def test_set_main_contact_requires_json_content_type(family, admin_caller):
    family_unit_id = family["family_unit"]["id"]
    admin_caller.headers.update({"Content-Type": "text/plain"})

    response = admin_caller.post(
        f"/api/v1/family-units/{family_unit_id}/main-contact",
        content=f'{{"contact_id": "{family["parent_a"]["id"]}"}}',
    )
    assert response.status_code == 415

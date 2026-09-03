"""HTTP contract tests for the read-only contacts endpoints."""

import os
from typing import Any
from uuid import UUID

import httpx
import psycopg
from psycopg.rows import dict_row


API_URL = os.environ["API_URL"]
DATABASE_URL = os.environ["DATABASE_URL"]
CONTACT_FIELDS = {"id", "first_name", "last_name", "email", "status", "can_login"}


def database_rows(query: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        return list(connection.execute(query, parameters).fetchall())


def serialise_contact(contact: dict[str, Any]) -> dict[str, Any]:
    return {
        **contact,
        "id": str(contact["id"]),
        "status": str(contact["status"]),
    }


def test_get_contacts_returns_first_page_in_name_order() -> None:
    expected_contacts = database_rows(
        """
        SELECT id, first_name, last_name, email, status, can_login
        FROM contacts
        ORDER BY last_name, first_name, id
        LIMIT 25
        """
    )
    total_contacts = database_rows("SELECT count(*) AS total FROM contacts")[0]["total"]

    response = httpx.get(f"{API_URL}/api/v1/contacts", timeout=5)

    assert response.status_code == 200
    assert response.json() == {
        "items": [serialise_contact(contact) for contact in expected_contacts],
        "page": 1,
        "page_size": 25,
        "total": total_contacts,
    }
    assert all(set(contact) == CONTACT_FIELDS for contact in response.json()["items"])


def test_get_contact_returns_matching_contact() -> None:
    contact = database_rows(
        """
        SELECT id, first_name, last_name, email, status, can_login
        FROM contacts
        ORDER BY id
        LIMIT 1
        """
    )[0]

    response = httpx.get(f"{API_URL}/api/v1/contacts/{contact['id']}", timeout=5)

    assert response.status_code == 200
    assert response.json() == serialise_contact(contact)


def test_get_contact_returns_404_for_unknown_uuid() -> None:
    unknown_contact_id = UUID("00000000-0000-0000-0000-000000000000")

    response = httpx.get(
        f"{API_URL}/api/v1/contacts/{unknown_contact_id}", timeout=5
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Contact not found"}


def test_get_contact_rejects_malformed_uuid() -> None:
    response = httpx.get(f"{API_URL}/api/v1/contacts/not-a-uuid", timeout=5)

    assert response.status_code == 422

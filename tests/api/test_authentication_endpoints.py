"""Contracts for protected endpoints and application sessions."""

import hashlib
import secrets

import httpx
import psycopg
import pytest
from psycopg.rows import dict_row

from .support import API_URL, DATABASE_URL


pytestmark = pytest.mark.contract


def test_crm_endpoint_requires_a_session() -> None:
    with httpx.Client() as client:
        response = client.get(f"{API_URL}/api/v1/contacts", timeout=5)

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_me_returns_the_authenticated_seeded_administrator() -> None:
    response = httpx.get(f"{API_URL}/api/v1/me", timeout=5)

    assert response.status_code == 200
    payload = response.json()
    assert payload["account_id"]
    assert payload["contact_id"]
    assert payload["first_name"]
    assert payload["last_name"]
    assert {role["role"] for role in payload["roles"]} >= {
        "Global System Administrator",
        "Area Manager",
        "Parent",
    }
    assert any(
        role["role"] == "Area Manager" and role["group"]
        for role in payload["roles"]
    )


def test_configured_authentication_providers_are_public() -> None:
    with httpx.Client() as client:
        response = client.get(f"{API_URL}/auth/providers", timeout=5)

    assert response.status_code == 200
    assert response.json() == {"providers": ["google", "microsoft"]}


@pytest.mark.parametrize("inactive_record", ("account", "contact"))
def test_active_session_is_rejected_when_its_owner_becomes_inactive(
    inactive_record: str,
) -> None:
    raw_session = secrets.token_urlsafe(48)
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        owner = connection.execute(
            """
            SELECT ua.id AS account_id, ua.contact_id
            FROM user_accounts ua
            JOIN contacts c ON c.id = ua.contact_id
            WHERE ua.status = 'active' AND c.status = 'active'
            ORDER BY ua.id
            LIMIT 1
            """
        ).fetchone()
        session_id = connection.execute(
            "INSERT INTO user_sessions (user_account_id, token_hash) VALUES (%s, %s) RETURNING id",
            (owner["account_id"], hashlib.sha256(raw_session.encode()).hexdigest()),
        ).fetchone()["id"]
        if inactive_record == "account":
            connection.execute(
                "UPDATE user_accounts SET status = 'suspended' WHERE id = %s",
                (owner["account_id"],),
            )
        else:
            connection.execute(
                "UPDATE contacts SET status = 'archived' WHERE id = %s",
                (owner["contact_id"],),
            )

    try:
        response = httpx.get(
            f"{API_URL}/api/v1/me",
            cookies={"crm_session": raw_session},
            timeout=5,
        )
        assert response.status_code == 401
        assert response.json() == {"detail": "Session is invalid or expired"}
    finally:
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute("DELETE FROM user_sessions WHERE id = %s", (session_id,))
            connection.execute(
                "UPDATE user_accounts SET status = 'active' WHERE id = %s",
                (owner["account_id"],),
            )
            connection.execute(
                "UPDATE contacts SET status = 'active' WHERE id = %s",
                (owner["contact_id"],),
            )

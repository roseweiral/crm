"""Invitation creation contracts for Global System Administrators."""

import os
from uuid import uuid4

import httpx
import psycopg
import pytest

from .support import API_URL, DATABASE_URL


pytestmark = pytest.mark.contract


def test_global_administrator_can_create_a_manual_invitation() -> None:
    with psycopg.connect(DATABASE_URL) as connection:
        contact_id = connection.execute(
            """
            INSERT INTO contacts (first_name, last_name, email, can_login)
            VALUES ('Invitation', 'Contract Test', %s, false)
            RETURNING id
            """,
            (f"invitation-{uuid4()}@crm-test.invalid",),
        ).fetchone()[0]

    response = httpx.post(
        f"{API_URL}/api/v1/invitations",
        json={"contact_id": str(contact_id)},
        cookies={"crm_session": os.environ["AUTH_TEST_SESSION_TOKEN"]},
        timeout=5,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["expires_in_days"] == 7
    assert "?invitation=" in payload["invitation_url"]

    with psycopg.connect(DATABASE_URL) as connection:
        account_id = connection.execute(
            "SELECT id FROM user_accounts WHERE contact_id = %s", (contact_id,)
        ).fetchone()[0]
        connection.execute("DELETE FROM invitations WHERE user_account_id = %s", (account_id,))
        connection.execute("DELETE FROM user_accounts WHERE id = %s", (account_id,))
        connection.execute("DELETE FROM contacts WHERE id = %s", (contact_id,))

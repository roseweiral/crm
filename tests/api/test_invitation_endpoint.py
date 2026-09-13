"""Invitation creation contracts for Global System Administrators."""

import os

import httpx
import pytest

from .support import API_URL


pytestmark = pytest.mark.contract


def test_global_administrator_can_create_a_manual_invitation(person) -> None:
    contact, account = person("invited")
    response = httpx.post(
        f"{API_URL}/api/v1/invitations",
        json={"contact_id": str(contact["id"])},
        cookies={"crm_session": os.environ["AUTH_TEST_SESSION_TOKEN"]},
        timeout=5,
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["expires_in_days"] == 7
    assert "?invitation=" in payload["invitation_url"]

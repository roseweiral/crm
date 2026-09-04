"""Contracts for protected endpoints and application sessions."""

import httpx
import pytest

from .support import API_URL


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

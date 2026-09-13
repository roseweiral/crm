"""Invitation and session contracts using real PostgreSQL transactions."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from .support import database_rows

pytestmark = pytest.mark.contract


def invite(records, account, email, **values):
    token = secrets.token_urlsafe(48)
    row = records(
        "invitations",
        user_account_id=account["id"],
        email=email,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        **values,
    )
    return token, row


def accept(callback_client, email, token, provider_name="google", **claims):
    client, provider = callback_client
    provider.claims = {
        "iss": "https://test-issuer.example",
        "sub": str(uuid4()),
        "email": email,
        "email_verified": True,
        **claims,
    }
    client.get(
        f"/auth/login/{provider_name}",
        params={"invitation": token},
        follow_redirects=False,
    )
    return client.get(f"/auth/callback/{provider_name}", follow_redirects=False)


@pytest.mark.parametrize("state", ["suspended", "closed"])
def test_invitation_cannot_reactivate_disabled_account(
    records, person, callback_client, state
):
    contact, account = person(state)
    token, invitation = invite(records, account, contact["email"])
    response = accept(callback_client, contact["email"], token)
    assert response.status_code == 403
    assert (
        database_rows(
            "SELECT status FROM user_accounts WHERE id = %s", (account["id"],)
        )[0]["status"]
        == state
    )
    assert (
        database_rows(
            "SELECT accepted_at FROM invitations WHERE id = %s", (invitation["id"],)
        )[0]["accepted_at"]
        is None
    )
    assert (
        database_rows(
            "SELECT id FROM user_identities WHERE user_account_id = %s",
            (account["id"],),
        )
        == []
    )
    assert (
        database_rows(
            "SELECT id FROM user_sessions WHERE user_account_id = %s", (account["id"],)
        )
        == []
    )


@pytest.mark.parametrize("verification", [False, None])
def test_microsoft_invitation_requires_verified_email(
    records, person, callback_client, verification
):
    contact, account = person("invited")
    token, _ = invite(records, account, contact["email"])
    response = accept(
        callback_client,
        contact["email"],
        token,
        "microsoft",
        email_verified=verification,
    )
    assert response.status_code == 401
    assert (
        database_rows(
            "SELECT id FROM user_identities WHERE user_account_id = %s",
            (account["id"],),
        )
        == []
    )


def test_preferred_username_is_not_a_verified_email(records, person, callback_client):
    contact, account = person("invited")
    token, _ = invite(records, account, contact["email"])
    response = accept(
        callback_client, None, token, "microsoft", preferred_username=contact["email"]
    )
    assert response.status_code == 401


@pytest.mark.parametrize("failure", ["exchange", "unverified"])
def test_failed_authentication_audit_survives_rollback(callback_client, failure):
    client, provider = callback_client
    subject = str(uuid4())
    if failure == "exchange":
        provider.error = ValueError("invalid token")
        event = "authentication.callback"
    else:
        provider.claims = {
            "iss": "https://test-issuer.example",
            "sub": subject,
            "email": "test@example.test",
            "email_verified": False,
        }
        event = "authentication.identity"
    before = database_rows(
        "SELECT count(*) AS n FROM audit_events WHERE event_type = %s AND outcome = %s",
        (event, "failure"),
    )[0]["n"]
    response = client.get("/auth/callback/google", follow_redirects=False)
    assert response.status_code == 401
    assert (
        database_rows(
            "SELECT count(*) AS n FROM audit_events WHERE event_type = %s AND outcome = %s",
            (event, "failure"),
        )[0]["n"]
        == before + 1
    )


@pytest.mark.parametrize("provider_name", ["google", "microsoft"])
def test_invitation_acceptance_is_atomic_and_single_use(
    records, person, callback_client, provider_name
):
    contact, account = person("invited")
    token, invitation = invite(records, account, contact["email"])
    response = accept(callback_client, contact["email"], token, provider_name)
    assert response.status_code == 307
    assert response.cookies.get("crm_session")
    assert (
        database_rows(
            "SELECT status FROM user_accounts WHERE id = %s", (account["id"],)
        )[0]["status"]
        == "active"
    )
    assert (
        database_rows(
            "SELECT accepted_at FROM invitations WHERE id = %s", (invitation["id"],)
        )[0]["accepted_at"]
        is not None
    )
    assert (
        len(
            database_rows(
                "SELECT id FROM user_identities WHERE user_account_id = %s",
                (account["id"],),
            )
        )
        == 1
    )
    assert (
        accept(callback_client, contact["email"], token, provider_name).status_code
        == 403
    )
    assert (
        len(
            database_rows(
                "SELECT id FROM user_sessions WHERE user_account_id = %s",
                (account["id"],),
            )
        )
        == 1
    )


@pytest.mark.parametrize("invalid", ["revoked", "expired", "email"])
def test_invalid_invitation_does_not_create_identity_or_session(
    records, person, callback_client, invalid
):
    contact, account = person("invited")
    now = datetime.now(timezone.utc)
    values = {"revoked_at": now} if invalid == "revoked" else {}
    if invalid == "expired":
        values = {
            "created_at": now - timedelta(days=8),
            "expires_at": now - timedelta(seconds=1),
        }
    token, invitation = invite(records, account, contact["email"], **values)
    email = "other@example.test" if invalid == "email" else contact["email"]
    assert accept(callback_client, email, token).status_code == 403
    assert (
        database_rows(
            "SELECT accepted_at FROM invitations WHERE id = %s", (invitation["id"],)
        )[0]["accepted_at"]
        is None
    )
    assert (
        database_rows(
            "SELECT id FROM user_identities WHERE user_account_id = %s",
            (account["id"],),
        )
        == []
    )
    assert (
        database_rows(
            "SELECT id FROM user_sessions WHERE user_account_id = %s", (account["id"],)
        )
        == []
    )


def test_sign_out_revokes_session_and_removes_cookie(
    person, session_token, callback_client
):
    _, account = person()
    client, _ = callback_client
    token = session_token(account["id"])
    client.cookies.set("crm_session", token)
    assert client.get("/api/v1/me").status_code == 200
    response = client.post("/auth/sign-out")
    assert response.status_code == 204
    assert "Max-Age=0" in response.headers["set-cookie"]
    client.cookies.set("crm_session", token)
    assert client.get("/api/v1/me").status_code == 401


@pytest.mark.parametrize("invalid", ["expired", "revoked"])
def test_invalid_session_is_rejected(person, session_token, callback_client, invalid):
    _, account = person()
    now = datetime.now(timezone.utc)
    values = (
        {"revoked_at": now}
        if invalid == "revoked"
        else {
            "created_at": now - timedelta(days=2),
            "expires_at": now - timedelta(days=1),
        }
    )
    token = session_token(account["id"], **values)
    client, _ = callback_client
    client.cookies.set("crm_session", token)
    assert client.get("/api/v1/me").status_code == 401


def test_closed_linked_account_cannot_be_reinvited(records, person, callback_client):
    import os

    contact, account = person("closed")
    records(
        "user_identities",
        user_account_id=account["id"],
        provider="google",
        issuer="https://test-issuer.example",
        subject=str(uuid4()),
        email=contact["email"],
        email_verified=True,
    )
    client, _ = callback_client
    client.cookies.set("crm_session", os.environ["AUTH_TEST_SESSION_TOKEN"])
    response = client.post(
        "/api/v1/invitations", json={"contact_id": str(contact["id"])}
    )
    assert response.status_code == 409
    assert (
        database_rows(
            "SELECT status FROM user_accounts WHERE id = %s", (account["id"],)
        )[0]["status"]
        == "closed"
    )


def test_linked_microsoft_identity_signs_in_without_email_claim(
    person, records, callback_client
):
    contact, account = person()
    subject = str(uuid4())
    records(
        "user_identities",
        user_account_id=account["id"],
        provider="microsoft",
        issuer="https://test-issuer.example",
        subject=subject,
        email=contact["email"],
        email_verified=True,
    )
    client, provider = callback_client
    provider.claims = {"iss": "https://test-issuer.example", "sub": subject}
    response = client.get("/auth/callback/microsoft", follow_redirects=False)
    assert response.status_code == 307
    assert response.cookies.get("crm_session")
    assert (
        database_rows(
            "SELECT email FROM user_identities WHERE user_account_id = %s",
            (account["id"],),
        )[0]["email"]
        == contact["email"]
    )

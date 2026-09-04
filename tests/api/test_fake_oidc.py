"""End-to-end authorization-code exchange against the fake OIDC provider."""

import httpx
import hashlib
import psycopg
import pytest
import secrets
from datetime import timedelta
from psycopg.rows import dict_row

from .support import API_URL, DATABASE_URL


pytestmark = pytest.mark.contract


def test_fake_oidc_signs_in_an_existing_identity() -> None:
    issued_session: str | None = None
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        identity = connection.execute(
            """
            SELECT ui.subject
            FROM user_accounts ua
            JOIN user_identities ui ON ui.user_account_id = ua.id
            JOIN user_access_role_assignments a ON a.user_account_id = ua.id
            JOIN access_roles ar ON ar.id = a.access_role_id
            WHERE ar.is_global
            LIMIT 1
            """
        ).fetchone()

    try:
        with httpx.Client(follow_redirects=False) as client:
            start = client.get(
                f"{API_URL}/auth/login/google",
                params={"login_hint": identity["subject"]},
            )
            assert start.status_code in {302, 307}
            authorised = client.get(start.headers["location"])
            assert authorised.status_code == 303
            callback = client.get(authorised.headers["location"])
            assert callback.status_code in {302, 307}
            issued_session = callback.cookies.get("crm_session")
            assert issued_session
            with psycopg.connect(DATABASE_URL) as connection:
                lifetime = connection.execute(
                    "SELECT expires_at - created_at FROM user_sessions WHERE token_hash = %s",
                    (hashlib.sha256(issued_session.encode()).hexdigest(),),
                ).fetchone()[0]
            assert lifetime == timedelta(hours=12)
    finally:
        with psycopg.connect(DATABASE_URL) as connection:
            if issued_session:
                connection.execute(
                    "DELETE FROM user_sessions WHERE token_hash = %s",
                    (hashlib.sha256(issued_session.encode()).hexdigest(),),
                )


def test_fake_oidc_rejects_an_invitation_at_or_after_expiry() -> None:
    invitation_token = secrets.token_urlsafe(48)
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        identity = connection.execute(
            """
            SELECT ui.*, ua.id AS account_id
            FROM user_identities ui
            JOIN user_accounts ua ON ua.id = ui.user_account_id
            WHERE NOT EXISTS (
              SELECT 1 FROM user_access_role_assignments assignment
              WHERE assignment.user_account_id = ua.id
            )
            ORDER BY ui.id
            LIMIT 1
            """
        ).fetchone()
        connection.execute("DELETE FROM user_identities WHERE id = %s", (identity["id"],))
        connection.execute(
            "UPDATE user_accounts SET status = 'invited' WHERE id = %s",
            (identity["account_id"],),
        )
        invitation_id = connection.execute(
            """
            INSERT INTO invitations (
              user_account_id, email, token_hash, created_at, expires_at
            ) VALUES (%s, %s, %s, now() - interval '2 days', now() - interval '1 day')
            RETURNING id
            """,
            (
                identity["account_id"],
                identity["email"],
                hashlib.sha256(invitation_token.encode()).hexdigest(),
            ),
        ).fetchone()["id"]

    try:
        with httpx.Client(follow_redirects=False) as client:
            start = client.get(
                f"{API_URL}/auth/login/google",
                params={"login_hint": identity["subject"], "invitation": invitation_token},
            )
            authorised = client.get(start.headers["location"])
            callback = client.get(authorised.headers["location"])
        assert callback.status_code == 403
        assert callback.json() == {"detail": "Invitation is invalid"}
    finally:
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute("DELETE FROM invitations WHERE id = %s", (invitation_id,))
            connection.execute(
                "UPDATE user_accounts SET status = 'active' WHERE id = %s",
                (identity["account_id"],),
            )
            connection.execute(
                """
                INSERT INTO user_identities (
                  id, user_account_id, provider, issuer, subject, email,
                  email_verified, last_signed_in_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    identity["id"], identity["user_account_id"], identity["provider"],
                    identity["issuer"], identity["subject"], identity["email"],
                    identity["email_verified"], identity["last_signed_in_at"],
                ),
            )

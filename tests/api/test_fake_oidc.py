"""End-to-end authorization-code exchange against the fake OIDC provider."""

import httpx
import hashlib
import psycopg
import pytest
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
    finally:
        with psycopg.connect(DATABASE_URL) as connection:
            if issued_session:
                connection.execute(
                    "DELETE FROM user_sessions WHERE token_hash = %s",
                    (hashlib.sha256(issued_session.encode()).hexdigest(),),
                )

"""Shared authenticated HTTP behavior for API tests."""

import os

import httpx
import pytest


@pytest.fixture(autouse=True)
def authenticated_http_get(monkeypatch: pytest.MonkeyPatch) -> None:
    original_get = httpx.get
    session_token = os.environ.get("AUTH_TEST_SESSION_TOKEN")
    if not session_token:
        return

    def get(*args, **kwargs):
        cookies = dict(kwargs.pop("cookies", {}))
        cookies.setdefault("crm_session", session_token)
        return original_get(*args, cookies=cookies, **kwargs)

    monkeypatch.setattr(httpx, "get", get)


@pytest.fixture
def records():
    """Committed, test-owned rows visible to HTTP requests; always remove them."""
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row

    created = []

    def insert(table, **values):
        with psycopg.connect(
            os.environ["DATABASE_URL"], row_factory=dict_row
        ) as connection:
            row = connection.execute(
                sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING *").format(
                    sql.Identifier(table),
                    sql.SQL(", ").join(map(sql.Identifier, values)),
                    sql.SQL(", ").join(sql.Placeholder() for _ in values),
                ),
                tuple(values.values()),
            ).fetchone()
        created.append((table, row["id"]))
        return row

    insert.track = lambda table, record_id: created.append((table, record_id))
    yield insert

    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        for table, record_id in reversed(created):
            if table == "user_accounts":
                # These rows can be created by the endpoint rather than the fixture.
                for dependent in (
                    "audit_events",
                    "user_sessions",
                    "user_identities",
                    "invitations",
                ):
                    connection.execute(
                        sql.SQL("DELETE FROM {} WHERE user_account_id = %s").format(
                            sql.Identifier(dependent)
                        ),
                        (record_id,),
                    )
            if table == "contacts":
                connection.execute(
                    "DELETE FROM audit_events WHERE details->>'invited_contact_id' = %s OR details->>'contact_id' = %s",
                    (str(record_id), str(record_id)),
                )
            connection.execute(
                sql.SQL("DELETE FROM {} WHERE id = %s").format(sql.Identifier(table)),
                (record_id,),
            )


@pytest.fixture
def person(records):
    from uuid import uuid4

    def create(status="active"):
        contact = records(
            "contacts",
            first_name="Test",
            last_name=str(uuid4()),
            email=f"{uuid4()}@example.test",
            can_login=True,
        )
        account = records("user_accounts", contact_id=contact["id"], status=status)
        return contact, account

    return create


@pytest.fixture
def session_token(records):
    import hashlib
    import secrets

    def create(account_id, **values):
        token = secrets.token_urlsafe(48)
        records(
            "user_sessions",
            user_account_id=account_id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            **values,
        )
        return token

    return create


@pytest.fixture
def callback_client(monkeypatch):
    """Exercise real routing and transactions, replacing only the OIDC exchange."""
    from fastapi.responses import RedirectResponse
    from fastapi.testclient import TestClient
    from main import app
    from routers import authentication as routes

    class Provider:
        claims = {}
        error = None

        async def authorize_redirect(self, request, redirect_uri, **parameters):
            return RedirectResponse(redirect_uri)

        async def authorize_access_token(self, request):
            if self.error:
                raise self.error
            return {"userinfo": self.claims}

    provider = Provider()
    monkeypatch.setattr(routes.oauth, "create_client", lambda name: provider)
    monkeypatch.setattr(routes, "enabled_providers", lambda: ["google", "microsoft"])
    from uuid import uuid4

    import psycopg

    user_agent = f"pytest-{uuid4()}"
    try:
        with TestClient(
            app, client=("127.0.0.1", 50000), headers={"user-agent": user_agent}
        ) as client:
            yield client, provider
    finally:
        with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
            connection.execute(
                "DELETE FROM audit_events WHERE user_agent = %s", (user_agent,)
            )

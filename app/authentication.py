"""OIDC configuration, CRM sessions, and authenticated request dependencies."""

from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, HTTPException, Request, status
from psycopg import Connection
from psycopg.types.json import Jsonb

from database import get_connection


SESSION_COOKIE = "crm_session"
SESSION_LIFETIME = timedelta(hours=12)
OIDC_PROVIDERS = ("google", "microsoft")
oauth = OAuth()


@dataclass(frozen=True)
class CurrentUser:
    account_id: UUID
    contact_id: UUID
    first_name: str
    last_name: str
    email: str | None
    session_id: UUID


def _provider_configuration(provider: str) -> dict[str, str] | None:
    prefix = provider.upper()
    metadata_url = os.environ.get(f"OIDC_{prefix}_METADATA_URL")
    client_id = os.environ.get(f"OIDC_{prefix}_CLIENT_ID")
    client_secret = os.environ.get(f"OIDC_{prefix}_CLIENT_SECRET")
    if not all((metadata_url, client_id, client_secret)):
        return None
    return {
        "server_metadata_url": metadata_url,
        "client_id": client_id,
        "client_secret": client_secret,
    }


def configure_oidc() -> None:
    """Register enabled providers from environment configuration."""
    for provider in OIDC_PROVIDERS:
        configuration = _provider_configuration(provider)
        if configuration is None or oauth.create_client(provider) is not None:
            continue
        oauth.register(
            name=provider,
            **configuration,
            client_kwargs={
                "scope": "openid email profile",
                "code_challenge_method": "S256",
                "token_endpoint_auth_method": "client_secret_post",
            },
        )


def enabled_providers() -> list[str]:
    return [
        provider
        for provider in OIDC_PROVIDERS
        if _provider_configuration(provider) is not None
    ]


def hash_secret_token(token: str) -> str:
    """Hash a high-entropy session or invitation secret for safe persistence."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(connection: Connection[Any], account_id: UUID) -> tuple[str, UUID]:
    raw_token = secrets.token_urlsafe(48)
    row = connection.execute(
        """
        INSERT INTO user_sessions (user_account_id, token_hash, expires_at)
        VALUES (%s, %s, now() + %s)
        RETURNING id
        """,
        (account_id, hash_secret_token(raw_token), SESSION_LIFETIME),
    ).fetchone()
    return raw_token, row["id"]


def audit_event(
    connection: Connection[Any],
    request: Request,
    event_type: str,
    outcome: str,
    *,
    account_id: UUID | None = None,
    provider: str | None = None,
    subject: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO audit_events (
          user_account_id, event_type, outcome, provider, subject,
          ip_address, user_agent, details
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            account_id,
            event_type,
            outcome,
            provider,
            subject,
            request.client.host if request.client else None,
            request.headers.get("user-agent"),
            Jsonb(details or {}),
        ),
    )


def get_current_user(
    request: Request,
    connection: Connection[Any] = Depends(get_connection),
) -> CurrentUser:
    raw_token = request.cookies.get(SESSION_COOKIE)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    row = connection.execute(
        """
        SELECT
          ua.id AS account_id,
          ua.contact_id,
          c.first_name,
          c.last_name,
          c.email,
          us.id AS session_id
        FROM user_sessions us
        JOIN user_accounts ua ON ua.id = us.user_account_id
        JOIN contacts c ON c.id = ua.contact_id
        WHERE us.token_hash = %s
          AND us.revoked_at IS NULL
          AND us.expires_at > now()
          AND ua.status = 'active'
          AND c.status <> 'archived'
        """,
        (hash_secret_token(raw_token),),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid or expired",
        )

    connection.execute(
        "UPDATE user_sessions SET last_seen_at = now() WHERE id = %s",
        (row["session_id"],),
    )
    return CurrentUser(**row)


def session_cookie_options() -> dict[str, Any]:
    return {
        "key": SESSION_COOKIE,
        "httponly": True,
        "secure": os.environ.get("APP_ENV") == "production",
        "samesite": "lax",
        "max_age": int(SESSION_LIFETIME.total_seconds()),
        "path": "/",
    }


configure_oidc()

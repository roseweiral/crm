"""Authentication entry points and current-session endpoints."""

from __future__ import annotations

import logging
import os
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from psycopg import Connection
from pydantic import BaseModel
from uuid import UUID

from authentication import (
    CurrentUser,
    audit_event,
    create_session,
    enabled_providers,
    get_current_user,
    oauth,
    session_cookie_options,
    token_hash,
)
from database import get_connection
from authorization import AuthorizationScope, get_authorization_scope


router = APIRouter(tags=["authentication"])
logger = logging.getLogger(__name__)


class UserRoleResponse(BaseModel):
    role: str
    group: str | None = None


class MeResponse(BaseModel):
    account_id: str
    contact_id: str
    first_name: str
    last_name: str
    email: str | None
    roles: list[UserRoleResponse]


class InvitationCreate(BaseModel):
    contact_id: UUID


class InvitationResponse(BaseModel):
    invitation_url: str
    expires_in_days: int = 7


@router.get("/auth/providers")
def get_providers() -> dict[str, list[str]]:
    return {"providers": enabled_providers()}


@router.get("/auth/login/{provider}")
async def login(
    provider: str,
    request: Request,
    invitation: str | None = Query(default=None),
    login_hint: str | None = Query(default=None),
) -> RedirectResponse:
    client = oauth.create_client(provider)
    if provider not in enabled_providers() or client is None:
        raise HTTPException(status_code=404, detail="Authentication provider not found")
    if invitation:
        request.session["invitation"] = invitation
    redirect_uri = str(request.url_for("auth_callback", provider=provider))
    parameters = {"login_hint": login_hint} if login_hint else {}
    return await client.authorize_redirect(request, redirect_uri, **parameters)


@router.get("/auth/callback/{provider}", name="auth_callback")
async def auth_callback(
    provider: str,
    request: Request,
    connection: Connection[Any] = Depends(get_connection),
) -> RedirectResponse:
    client = oauth.create_client(provider)
    if provider not in enabled_providers() or client is None:
        raise HTTPException(status_code=404, detail="Authentication provider not found")

    try:
        token = await client.authorize_access_token(request)
        claims = dict(token["userinfo"])
    except Exception as error:
        logger.exception("OIDC callback failed for provider %s", provider)
        audit_event(
            connection,
            request,
            "authentication.callback",
            "failure",
            provider=provider,
            details={"reason": type(error).__name__},
        )
        raise HTTPException(status_code=401, detail="Authentication failed") from error

    issuer = str(claims.get("iss", ""))
    subject = str(claims.get("sub", ""))
    email = str(claims.get("email") or claims.get("preferred_username") or "").strip().lower()
    verified_email = claims.get("email_verified") is True or (
        provider == "microsoft" and bool(email)
    )
    if not issuer or not subject or not email or not verified_email:
        audit_event(
            connection,
            request,
            "authentication.identity",
            "failure",
            provider=provider,
            subject=subject or None,
            details={"reason": "verified_email_required"},
        )
        raise HTTPException(status_code=401, detail="A verified email is required")

    identity = connection.execute(
        """
        SELECT ui.user_account_id
        FROM user_identities ui
        WHERE ui.issuer = %s AND ui.subject = %s AND ui.provider = %s
        """,
        (issuer, subject, provider),
    ).fetchone()

    if identity is None:
        invitation_token = request.session.pop("invitation", None)
        if not invitation_token:
            raise HTTPException(status_code=403, detail="An invitation is required")
        invitation = connection.execute(
            """
            SELECT id, user_account_id, email
            FROM invitations
            WHERE token_hash = %s
              AND accepted_at IS NULL
              AND revoked_at IS NULL
              AND expires_at > now()
            FOR UPDATE
            """,
            (token_hash(invitation_token),),
        ).fetchone()
        if invitation is None or invitation["email"] != email:
            raise HTTPException(status_code=403, detail="Invitation is invalid")
        connection.execute(
            """
            INSERT INTO user_identities (
              user_account_id, provider, issuer, subject, email, email_verified,
              last_signed_in_at
            ) VALUES (%s, %s, %s, %s, %s, true, now())
            """,
            (invitation["user_account_id"], provider, issuer, subject, email),
        )
        connection.execute(
            "UPDATE invitations SET accepted_at = now() WHERE id = %s",
            (invitation["id"],),
        )
        connection.execute(
            "UPDATE user_accounts SET status = 'active' WHERE id = %s",
            (invitation["user_account_id"],),
        )
        account_id = invitation["user_account_id"]
    else:
        account_id = identity["user_account_id"]
        connection.execute(
            """
            UPDATE user_identities
            SET email = %s, email_verified = true, last_signed_in_at = now()
            WHERE user_account_id = %s
            """,
            (email, account_id),
        )

    account = connection.execute(
        """
        SELECT ua.status, c.status AS contact_status
        FROM user_accounts ua
        JOIN contacts c ON c.id = ua.contact_id
        WHERE ua.id = %s
        """,
        (account_id,),
    ).fetchone()
    if account is None or account["status"] != "active" or account["contact_status"] == "archived":
        raise HTTPException(status_code=403, detail="Account is not active")

    raw_session, _ = create_session(connection, account_id)
    audit_event(
        connection,
        request,
        "authentication.sign_in",
        "success",
        account_id=account_id,
        provider=provider,
        subject=subject,
    )
    response = RedirectResponse(os.environ.get("FRONTEND_URL", "http://localhost:5173"))
    response.set_cookie(value=raw_session, **session_cookie_options())
    return response


@router.get("/api/v1/me", response_model=MeResponse)
def me(
    user: CurrentUser = Depends(get_current_user),
    connection: Connection[Any] = Depends(get_connection),
) -> MeResponse:
    roles = connection.execute(
        """
        SELECT ar.name AS role, NULL::varchar AS group_name
        FROM user_access_role_assignments assignment
        JOIN access_roles ar ON ar.id = assignment.access_role_id
        WHERE assignment.user_account_id = %s
          AND assignment.start_date <= current_date
          AND (assignment.end_date IS NULL OR assignment.end_date >= current_date)

        UNION

        SELECT rt.name AS role, g.name AS group_name
        FROM contact_roles_groups assignment
        JOIN role_types rt ON rt.id = assignment.role_type_id
        JOIN groups g ON g.id = assignment.group_id
        WHERE assignment.contact_id = %s
          AND assignment.start_date <= current_date
          AND (assignment.end_date IS NULL OR assignment.end_date >= current_date)

        UNION

        SELECT initcap(relationship::text) AS role, NULL::varchar AS group_name
        FROM contact_family_units
        WHERE contact_id = %s

        ORDER BY role, group_name NULLS FIRST
        """,
        (user.account_id, user.contact_id, user.contact_id),
    ).fetchall()
    return MeResponse(
        account_id=str(user.account_id),
        contact_id=str(user.contact_id),
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        roles=[
            UserRoleResponse(role=row["role"], group=row["group_name"])
            for row in roles
        ],
    )


@router.post("/api/v1/invitations", response_model=InvitationResponse, status_code=201)
def create_invitation(
    payload: InvitationCreate,
    request: Request,
    scope: AuthorizationScope = Depends(get_authorization_scope),
    connection: Connection[Any] = Depends(get_connection),
) -> InvitationResponse:
    if not scope.is_global_administrator:
        raise HTTPException(status_code=403, detail="Global administrator access required")
    contact = connection.execute(
        "SELECT id, email, status FROM contacts WHERE id = %s",
        (payload.contact_id,),
    ).fetchone()
    if contact is None or contact["status"] == "archived" or not contact["email"]:
        raise HTTPException(status_code=400, detail="Contact must be active and have an email")
    account = connection.execute(
        """
        INSERT INTO user_accounts (contact_id, status)
        VALUES (%s, 'invited')
        ON CONFLICT (contact_id) DO UPDATE
          SET status = CASE
            WHEN user_accounts.status = 'closed' THEN 'invited'::user_account_status
            ELSE user_accounts.status
          END
        RETURNING id, status
        """,
        (payload.contact_id,),
    ).fetchone()
    if account["status"] == "active":
        raise HTTPException(status_code=409, detail="Contact already has an active account")
    connection.execute(
        """
        UPDATE invitations
        SET revoked_at = now()
        WHERE user_account_id = %s AND accepted_at IS NULL AND revoked_at IS NULL
        """,
        (account["id"],),
    )
    raw_token = secrets.token_urlsafe(48)
    connection.execute(
        """
        INSERT INTO invitations (
          user_account_id, invited_by_user_account_id, email, token_hash
        ) VALUES (%s, %s, %s, %s)
        """,
        (account["id"], scope.user.account_id, contact["email"].lower(), token_hash(raw_token)),
    )
    audit_event(
        connection,
        request,
        "invitation.created",
        "success",
        account_id=scope.user.account_id,
        details={"invited_contact_id": str(payload.contact_id)},
    )
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    return InvitationResponse(invitation_url=f"{frontend_url}/?invitation={raw_token}")


@router.post(
    "/auth/sign-out",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def sign_out(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    connection: Connection[Any] = Depends(get_connection),
) -> Response:
    connection.execute(
        "UPDATE user_sessions SET revoked_at = now() WHERE id = %s",
        (user.session_id,),
    )
    audit_event(
        connection,
        request,
        "authentication.sign_out",
        "success",
        account_id=user.account_id,
    )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(key="crm_session", path="/")
    return response

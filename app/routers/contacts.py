"""Read-only contact endpoints."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg import Connection

from database import get_connection
from authorization import AuthorizationScope, get_authorization_scope
from models.contacts import Contact, ContactDetail, ContactPage


router = APIRouter(prefix="/contacts", tags=["contacts"])

CONTACT_COLUMNS = "id, first_name, last_name, email, status, can_login"


@router.get("", response_model=ContactPage)
def get_contacts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    scope: AuthorizationScope = Depends(get_authorization_scope),
    connection: Connection[Any] = Depends(get_connection),
) -> ContactPage:
    """Return one page of contacts in stable name order."""
    offset = (page - 1) * page_size

    where_clause = ""
    parameters: list[Any] = []
    if not scope.is_global_administrator:
        where_clause = "WHERE id = ANY(%s)"
        parameters.append(list(scope.contact_ids))
    total = connection.execute(
        f"SELECT count(*) AS total FROM contacts {where_clause}", parameters
    ).fetchone()["total"]
    rows = connection.execute(
        f"""
        SELECT {CONTACT_COLUMNS}
        FROM contacts
        {where_clause}
        ORDER BY last_name, first_name, id
        LIMIT %s OFFSET %s
        """,
        (*parameters, page_size, offset),
    ).fetchall()

    return ContactPage(
        items=[Contact.model_validate(row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{contact_id}", response_model=ContactDetail)
def get_contact(
    contact_id: UUID,
    scope: AuthorizationScope = Depends(get_authorization_scope),
    connection: Connection[Any] = Depends(get_connection),
) -> ContactDetail:
    """Return a contact by UUID."""
    row = connection.execute(
        f"""
        SELECT {CONTACT_COLUMNS}, created_at, modified_at
        FROM contacts
        WHERE id = %s
        """,
        (contact_id,),
    ).fetchone()

    if row is None or (
        not scope.is_global_administrator and contact_id not in scope.contact_ids
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )

    return ContactDetail.model_validate(row)

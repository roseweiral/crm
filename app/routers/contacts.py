"""Read-only contact endpoints."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg import Connection

from database import get_connection
from models.contacts import Contact, ContactDetail, ContactPage


router = APIRouter(prefix="/contacts", tags=["contacts"])

CONTACT_COLUMNS = "id, first_name, last_name, email, status, can_login"


@router.get("", response_model=ContactPage)
def get_contacts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    connection: Connection[Any] = Depends(get_connection),
) -> ContactPage:
    """Return one page of contacts in stable name order."""
    offset = (page - 1) * page_size

    total = connection.execute("SELECT count(*) AS total FROM contacts").fetchone()[
        "total"
    ]
    rows = connection.execute(
        f"""
        SELECT {CONTACT_COLUMNS}
        FROM contacts
        ORDER BY last_name, first_name, id
        LIMIT %s OFFSET %s
        """,
        (page_size, offset),
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

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )

    return ContactDetail.model_validate(row)

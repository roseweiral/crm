"""Read-only contact role/group assignment endpoints."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg import Connection

from database import get_connection
from models.contact_role_groups import ContactRoleGroup, ContactRoleGroupPage


router = APIRouter(prefix="/contact-role-groups", tags=["contact role groups"])
ASSIGNMENT_COLUMNS = (
    "id, contact_id, role_type_id, group_id, start_date, end_date"
)


@router.get("", response_model=ContactRoleGroupPage)
def get_contact_role_groups(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    connection: Connection[Any] = Depends(get_connection),
) -> ContactRoleGroupPage:
    """Return one page of role/group assignments in stable date order."""
    offset = (page - 1) * page_size
    total = connection.execute(
        "SELECT count(*) AS total FROM contact_roles_groups"
    ).fetchone()["total"]
    rows = connection.execute(
        f"""
        SELECT {ASSIGNMENT_COLUMNS}
        FROM contact_roles_groups
        ORDER BY start_date, id
        LIMIT %s OFFSET %s
        """,
        (page_size, offset),
    ).fetchall()

    return ContactRoleGroupPage(
        items=[ContactRoleGroup.model_validate(row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{contact_role_group_id}", response_model=ContactRoleGroup)
def get_contact_role_group(
    contact_role_group_id: UUID,
    connection: Connection[Any] = Depends(get_connection),
) -> ContactRoleGroup:
    """Return one contact role/group assignment by UUID."""
    row = connection.execute(
        f"""
        SELECT {ASSIGNMENT_COLUMNS}
        FROM contact_roles_groups
        WHERE id = %s
        """,
        (contact_role_group_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact role group not found",
        )
    return ContactRoleGroup.model_validate(row)

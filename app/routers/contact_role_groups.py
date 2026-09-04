"""Read-only contact role/group assignment endpoints."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg import Connection

from database import get_connection
from authorization import AuthorizationScope, get_authorization_scope
from models.contact_role_groups import (
    ContactRoleGroup,
    ContactRoleGroupDetail,
    ContactRoleGroupPage,
)


router = APIRouter(prefix="/contact-role-groups", tags=["contact role groups"])
ASSIGNMENT_COLUMNS = """
  crg.id,
  crg.contact_id,
  c.first_name AS contact_first_name,
  c.last_name AS contact_last_name,
  crg.role_type_id,
  rt.name AS role_type_name,
  crg.group_id,
  g.name AS group_name,
  crg.start_date,
  crg.end_date
"""
ASSIGNMENT_JOINS = """
  FROM contact_roles_groups crg
  JOIN contacts c ON c.id = crg.contact_id
  JOIN role_types rt ON rt.id = crg.role_type_id
  JOIN groups g ON g.id = crg.group_id
"""


@router.get("", response_model=ContactRoleGroupPage)
def get_contact_role_groups(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    contact_id: UUID | None = Query(default=None),
    group_id: UUID | None = Query(default=None),
    role_type_id: UUID | None = Query(default=None),
    scope: AuthorizationScope = Depends(get_authorization_scope),
    connection: Connection[Any] = Depends(get_connection),
) -> ContactRoleGroupPage:
    """Return one page of role/group assignments in stable date order."""
    offset = (page - 1) * page_size
    filters: list[str] = []
    parameters: list[Any] = []
    for column, value in (
        ("contact_id", contact_id),
        ("group_id", group_id),
        ("role_type_id", role_type_id),
    ):
        if value is not None:
            filters.append(f"crg.{column} = %s")
            parameters.append(value)
    if not scope.is_global_administrator:
        filters.append("crg.contact_id = ANY(%s)")
        parameters.append(list(scope.contact_ids))
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    total = connection.execute(
        f"SELECT count(*) AS total FROM contact_roles_groups crg {where_clause}",
        parameters,
    ).fetchone()["total"]
    rows = connection.execute(
        f"""
        SELECT {ASSIGNMENT_COLUMNS}
        {ASSIGNMENT_JOINS}
        {where_clause}
        ORDER BY crg.start_date, crg.id
        LIMIT %s OFFSET %s
        """,
        (*parameters, page_size, offset),
    ).fetchall()

    return ContactRoleGroupPage(
        items=[ContactRoleGroup.model_validate(row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{contact_role_group_id}", response_model=ContactRoleGroupDetail)
def get_contact_role_group(
    contact_role_group_id: UUID,
    scope: AuthorizationScope = Depends(get_authorization_scope),
    connection: Connection[Any] = Depends(get_connection),
) -> ContactRoleGroupDetail:
    """Return one contact role/group assignment by UUID."""
    row = connection.execute(
        f"""
        SELECT {ASSIGNMENT_COLUMNS}, crg.created_at, crg.modified_at
        {ASSIGNMENT_JOINS}
        WHERE crg.id = %s
        """,
        (contact_role_group_id,),
    ).fetchone()
    if row is None or (
        not scope.is_global_administrator
        and row["contact_id"] not in scope.contact_ids
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact role group not found",
        )
    return ContactRoleGroupDetail.model_validate(row)

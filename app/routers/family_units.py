"""Read-only family-unit endpoints."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg import Connection

from database import get_connection
from authorization import AuthorizationService, get_authorization_service
from models.family_units import (
    FamilyMember,
    FamilyUnit,
    FamilyUnitDetail,
    FamilyUnitPage,
)


router = APIRouter(prefix="/family-units", tags=["family units"])


@router.get("", response_model=FamilyUnitPage)
def get_family_units(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> FamilyUnitPage:
    """Return one page of family units in stable UUID order."""
    offset = (page - 1) * page_size
    where_clause = ""
    parameters: list[Any] = []
    # Only this fixed fragment is interpolated; every value remains a DB parameter.
    scope = authorization.scope("family:view")
    if not scope.unrestricted:
        where_clause = "WHERE id = ANY(%s)"
        parameters.append(list(scope.ids))
    total = connection.execute(
        f"SELECT count(*) AS total FROM family_units {where_clause}", parameters
    ).fetchone()["total"]
    rows = connection.execute(
        f"SELECT id FROM family_units {where_clause} ORDER BY id LIMIT %s OFFSET %s",
        (*parameters, page_size, offset),
    ).fetchall()

    return FamilyUnitPage(
        items=[FamilyUnit.model_validate(row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{family_unit_id}", response_model=FamilyUnitDetail)
def get_family_unit(
    family_unit_id: UUID,
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> FamilyUnitDetail:
    """Return a family unit with all associated members and relationships."""
    family_unit = connection.execute(
        """
        SELECT id, created_at, modified_at
        FROM family_units
        WHERE id = %s
        """,
        (family_unit_id,),
    ).fetchone()
    if family_unit is None or (
        not authorization.allows("family:view", family_unit_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family unit not found",
        )

    rows = connection.execute(
        """
        SELECT
          c.id AS contact_id,
          c.first_name,
          c.last_name,
          cfu.relationship
        FROM contact_family_units cfu
        JOIN contacts c ON c.id = cfu.contact_id
        WHERE cfu.family_unit_id = %s
        ORDER BY c.last_name, c.first_name, c.id
        """,
        (family_unit_id,),
    ).fetchall()

    return FamilyUnitDetail(
        id=family_unit["id"],
        created_at=family_unit["created_at"],
        modified_at=family_unit["modified_at"],
        members=[FamilyMember.model_validate(row) for row in rows],
    )

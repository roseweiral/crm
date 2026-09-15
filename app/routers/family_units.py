"""Family-unit reads and Main Contact tracking.

See documents/api-contract.md "Main Contact tracking" for the write
endpoint's full contract.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from psycopg import Connection

from authentication import audit_event
from authorization import AuthorizationService, get_authorization_service
from database import get_connection
from models.family_units import (
    FamilyMember,
    FamilyUnit,
    FamilyUnitDetail,
    FamilyUnitPage,
    SetMainContact,
)
from write_security import require_json_write

router = APIRouter(prefix="/family-units", tags=["family units"])


def _family_unit_detail(family_unit_id: UUID, connection: Connection[Any]) -> FamilyUnitDetail | None:
    family_unit = connection.execute(
        """
        SELECT id, created_at, modified_at
        FROM family_units
        WHERE id = %s
        """,
        (family_unit_id,),
    ).fetchone()
    if family_unit is None:
        return None

    rows = connection.execute(
        """
        SELECT
          c.id AS contact_id,
          c.first_name,
          c.last_name,
          cfu.relationship,
          (cfmc.contact_id IS NOT NULL) AS is_main_contact
        FROM contact_family_units cfu
        JOIN contacts c ON c.id = cfu.contact_id
        LEFT JOIN contact_family_main_contacts cfmc
          ON cfmc.family_unit_id = cfu.family_unit_id
         AND cfmc.contact_id = cfu.contact_id
         AND cfmc.end_date IS NULL
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
    detail = _family_unit_detail(family_unit_id, connection)
    if detail is None or not authorization.allows("family:view", family_unit_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family unit not found",
        )
    return detail


@router.post(
    "/{family_unit_id}/main-contact",
    response_model=FamilyUnitDetail,
    dependencies=[Depends(require_json_write)],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Write permission or CSRF validation failed"},
        404: {"description": "Family unit not found"},
        415: {"description": "Content-Type must be application/json"},
        422: {"description": "contact_id is not a current, non-child member of this family unit"},
    },
)
def set_main_contact(
    family_unit_id: UUID,
    payload: SetMainContact,
    request: Request,
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> FamilyUnitDetail:
    """Change who currently holds Main Contact status for a family unit.

    Ends the previous holder's tenure and starts the new one atomically,
    revoking the outgoing holder's sessions the same way archiving a
    contact does. Setting the already-current holder again is a no-op.
    """
    authorization.require("family:manage-main-contact", family_unit_id)

    family_unit = connection.execute(
        "SELECT id FROM family_units WHERE id = %s FOR UPDATE",
        (family_unit_id,),
    ).fetchone()
    if family_unit is None:
        raise HTTPException(status_code=404, detail="Family unit not found")

    member = connection.execute(
        """
        SELECT contact_id FROM contact_family_units
        WHERE family_unit_id = %s AND contact_id = %s AND relationship <> 'child'
        """,
        (family_unit_id, payload.contact_id),
    ).fetchone()
    if member is None:
        raise HTTPException(
            status_code=422,
            detail="contact_id must be a current, non-child member of this family unit",
        )

    current = connection.execute(
        """
        SELECT contact_id FROM contact_family_main_contacts
        WHERE family_unit_id = %s AND end_date IS NULL
        """,
        (family_unit_id,),
    ).fetchone()

    if current is None or current["contact_id"] != payload.contact_id:
        if current is not None:
            connection.execute(
                """
                UPDATE contact_family_main_contacts SET end_date = current_date
                WHERE family_unit_id = %s AND end_date IS NULL
                """,
                (family_unit_id,),
            )
            connection.execute(
                """UPDATE user_sessions SET revoked_at = now()
                   WHERE user_account_id IN (SELECT id FROM user_accounts WHERE contact_id = %s)
                     AND revoked_at IS NULL""",
                (current["contact_id"],),
            )
        connection.execute(
            "INSERT INTO contact_family_main_contacts (family_unit_id, contact_id) VALUES (%s, %s)",
            (family_unit_id, payload.contact_id),
        )
        audit_event(
            connection,
            request,
            "family.main_contact_changed",
            "success",
            account_id=authorization.user.account_id,
            details={
                "family_unit_id": str(family_unit_id),
                "outgoing_contact_id": str(current["contact_id"]) if current else None,
                "incoming_contact_id": str(payload.contact_id),
            },
        )

    detail = _family_unit_detail(family_unit_id, connection)
    assert detail is not None  # just locked and confirmed to exist above
    return detail

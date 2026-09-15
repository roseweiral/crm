"""Contact emergency contact reads, writes, and deletion.

See documents/api-contract.md "Emergency contact" for the full behavioral
contract. Reading requires contact:view-sensitive (not contact:view);
writing uses the same self/Main-Contact/Group-Leader-family model as
phone numbers and addresses. This is the one resource in the system with
a genuine hard DELETE - the table deliberately carries no start_date/
end_date, since this session didn't ask for a queryable history of past
emergency contacts.
"""

import hashlib
import re
from typing import Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
)
from psycopg import Connection, sql
from psycopg.errors import ForeignKeyViolation, UniqueViolation

from authentication import audit_event
from authorization import AuthorizationService, get_authorization_service
from database import get_connection
from models.emergency_contacts import (
    ContactEmergencyContact,
    ContactEmergencyContactCreate,
    ContactEmergencyContactDetail,
    ContactEmergencyContactPage,
    ContactEmergencyContactPatch,
)
from write_security import require_json_write, require_write

router = APIRouter(tags=["contact emergency contacts"])

COLUMNS = "id, contact_id, emergency_contact_id, priority, relationship"

WRITE_ERRORS = {
    401: {"description": "Authentication required"},
    403: {"description": "Write permission or CSRF validation failed"},
    409: {"description": "priority or emergency_contact_id already used for this contact_id"},
    415: {"description": "Content-Type must be application/json"},
    422: {
        "description": "contact_id equals emergency_contact_id, or emergency_contact_id "
        "does not refer to an existing contact"
    },
}
ETAG_HEADER = {
    "description": "Opaque strong version tag for If-Match",
    "schema": {"type": "string"},
}


def _etag(model: ContactEmergencyContactDetail) -> str:
    return '"' + hashlib.sha256(model.model_dump_json().encode()).hexdigest() + '"'


def _check_if_match(if_match: str | None) -> None:
    if if_match is None:
        raise HTTPException(status_code=428, detail="If-Match is required")
    if not re.fullmatch(r'"[!#-~]+"', if_match) or "," in if_match:
        raise HTTPException(status_code=422, detail="If-Match must be one strong ETag")


def _response(row: dict[str, Any], response: Response) -> ContactEmergencyContactDetail:
    detail = ContactEmergencyContactDetail.model_validate(row)
    response.headers["ETag"] = _etag(detail)
    return detail


@router.get("/contact-emergency-contacts", response_model=ContactEmergencyContactPage)
def get_contact_emergency_contacts(
    contact_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> ContactEmergencyContactPage:
    """Return one page of emergency contacts, optionally filtered by contact_id."""
    offset = (page - 1) * page_size
    scope = authorization.scope("contact:view-sensitive")
    conditions = []
    parameters: list[Any] = []
    if not scope.unrestricted:
        conditions.append("contact_id = ANY(%s)")
        parameters.append(list(scope.ids))
    if contact_id is not None:
        conditions.append("contact_id = %s")
        parameters.append(contact_id)
    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    total = connection.execute(
        f"SELECT count(*) AS total FROM contact_emergency_contacts {where_clause}", parameters
    ).fetchone()["total"]
    rows = connection.execute(
        f"""
        SELECT {COLUMNS}
        FROM contact_emergency_contacts
        {where_clause}
        ORDER BY contact_id, priority
        LIMIT %s OFFSET %s
        """,
        (*parameters, page_size, offset),
    ).fetchall()

    return ContactEmergencyContactPage(
        items=[ContactEmergencyContact.model_validate(row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/contact-emergency-contacts/{emergency_contact_id}",
    response_model=ContactEmergencyContactDetail,
    responses={200: {"headers": {"ETag": ETAG_HEADER}}},
)
def get_contact_emergency_contact(
    emergency_contact_id: UUID,
    response: Response,
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> ContactEmergencyContactDetail:
    """Return an emergency contact entry by UUID."""
    row = connection.execute(
        f"SELECT {COLUMNS}, created_at, modified_at FROM contact_emergency_contacts WHERE id = %s",
        (emergency_contact_id,),
    ).fetchone()

    if row is None or not authorization.allows("contact:view-sensitive", row["contact_id"]):
        raise HTTPException(status_code=404, detail="Emergency contact not found")

    return _response(row, response)


@router.post(
    "/contact-emergency-contacts",
    response_model=ContactEmergencyContactDetail,
    status_code=201,
    dependencies=[Depends(require_json_write)],
    responses={
        **WRITE_ERRORS,
        201: {
            "headers": {
                "ETag": ETAG_HEADER,
                "Location": {
                    "description": "Relative emergency contact detail URL",
                    "schema": {"type": "string"},
                },
            }
        },
    },
)
def create_contact_emergency_contact(
    payload: ContactEmergencyContactCreate,
    request: Request,
    response: Response,
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> ContactEmergencyContactDetail:
    """Create an emergency contact entry."""
    authorization.require("contact-emergency-contact:update", payload.contact_id)
    try:
        row = connection.execute(
            f"""
            INSERT INTO contact_emergency_contacts
              (contact_id, emergency_contact_id, priority, relationship)
            VALUES (%s, %s, %s, %s)
            RETURNING {COLUMNS}, created_at, modified_at
            """,
            (payload.contact_id, payload.emergency_contact_id, payload.priority, payload.relationship),
        ).fetchone()
    except UniqueViolation as error:
        raise HTTPException(
            status_code=409,
            detail="priority or emergency_contact_id already used for this contact_id",
        ) from error
    except ForeignKeyViolation as error:
        raise HTTPException(
            status_code=422,
            detail="emergency_contact_id does not refer to an existing contact",
        ) from error
    audit_event(
        connection,
        request,
        "contact_emergency_contact.created",
        "success",
        account_id=authorization.user.account_id,
        details={
            "contact_emergency_contact_id": str(row["id"]),
            "contact_id": str(payload.contact_id),
        },
    )
    response.headers["Location"] = f"/api/v1/contact-emergency-contacts/{row['id']}"
    return _response(row, response)


@router.patch(
    "/contact-emergency-contacts/{emergency_contact_id}",
    response_model=ContactEmergencyContactDetail,
    dependencies=[Depends(require_json_write)],
    responses={
        **WRITE_ERRORS,
        404: {"description": "Emergency contact not found"},
        412: {"description": "Emergency contact changed; refetch before retrying"},
        428: {"description": "If-Match is required"},
        200: {"headers": {"ETag": ETAG_HEADER}},
    },
)
def update_contact_emergency_contact(
    emergency_contact_id: UUID,
    payload: ContactEmergencyContactPatch,
    request: Request,
    response: Response,
    if_match: str | None = Header(
        default=None,
        description="One quoted strong ETag from the entry's GET or last write. Required; missing returns 428.",
    ),
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> ContactEmergencyContactDetail:
    """Change supplied fields atomically."""
    current = connection.execute(
        f"SELECT {COLUMNS}, created_at, modified_at FROM contact_emergency_contacts WHERE id = %s FOR UPDATE",
        (emergency_contact_id,),
    ).fetchone()
    if current is None:
        raise HTTPException(status_code=404, detail="Emergency contact not found")
    authorization.require("contact-emergency-contact:update", current["contact_id"])
    _check_if_match(if_match)
    if if_match != _etag(ContactEmergencyContactDetail.model_validate(current)):
        raise HTTPException(
            status_code=412, detail="Emergency contact has changed; fetch it before retrying"
        )
    changes = payload.model_dump(exclude_unset=True, mode="json")
    if (
        "emergency_contact_id" in changes
        and changes["emergency_contact_id"] == str(current["contact_id"])
    ):
        raise HTTPException(
            status_code=422, detail="contact_id and emergency_contact_id must differ"
        )
    assignments = sql.SQL(", ").join(
        sql.SQL("{} = %s").format(sql.Identifier(field)) for field in changes
    )
    try:
        row = connection.execute(
            sql.SQL(
                "UPDATE contact_emergency_contacts SET {} WHERE id = %s RETURNING "
                + COLUMNS
                + ", created_at, modified_at"
            ).format(assignments),
            (*changes.values(), emergency_contact_id),
        ).fetchone()
    except UniqueViolation as error:
        raise HTTPException(
            status_code=409,
            detail="priority or emergency_contact_id already used for this contact_id",
        ) from error
    except ForeignKeyViolation as error:
        raise HTTPException(
            status_code=422,
            detail="emergency_contact_id does not refer to an existing contact",
        ) from error
    audit_event(
        connection,
        request,
        "contact_emergency_contact.updated",
        "success",
        account_id=authorization.user.account_id,
        details={
            "contact_emergency_contact_id": str(emergency_contact_id),
            "contact_id": str(current["contact_id"]),
            "fields": sorted(changes),
        },
    )
    return _response(row, response)


@router.delete(
    "/contact-emergency-contacts/{emergency_contact_id}",
    status_code=204,
    dependencies=[Depends(require_write)],
    responses={
        401: WRITE_ERRORS[401],
        403: WRITE_ERRORS[403],
        404: {"description": "Emergency contact not found"},
        412: {"description": "Emergency contact changed; refetch before retrying"},
        428: {"description": "If-Match is required"},
    },
)
def delete_contact_emergency_contact(
    emergency_contact_id: UUID,
    request: Request,
    if_match: str | None = Header(
        default=None,
        description="One quoted strong ETag from the entry's GET or last write. Required; missing returns 428.",
    ),
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> Response:
    """Permanently remove an emergency contact entry - the one hard delete in this system."""
    current = connection.execute(
        f"SELECT {COLUMNS}, created_at, modified_at FROM contact_emergency_contacts WHERE id = %s FOR UPDATE",
        (emergency_contact_id,),
    ).fetchone()
    if current is None:
        raise HTTPException(status_code=404, detail="Emergency contact not found")
    authorization.require("contact-emergency-contact:update", current["contact_id"])
    _check_if_match(if_match)
    if if_match != _etag(ContactEmergencyContactDetail.model_validate(current)):
        raise HTTPException(
            status_code=412, detail="Emergency contact has changed; fetch it before retrying"
        )
    connection.execute(
        "DELETE FROM contact_emergency_contacts WHERE id = %s", (emergency_contact_id,)
    )
    audit_event(
        connection,
        request,
        "contact_emergency_contact.deleted",
        "success",
        account_id=authorization.user.account_id,
        details={
            "contact_emergency_contact_id": str(emergency_contact_id),
            "contact_id": str(current["contact_id"]),
        },
    )
    return Response(status_code=204)

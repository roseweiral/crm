"""Contact reads and administrator-managed creation and partial editing."""

import hashlib
import re
from typing import Any
from uuid import UUID

from authentication import audit_event
from authorization import AuthorizationService, get_authorization_service
from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from models.contacts import (
    CORE_CONTACT_FIELDS,
    PERSONAL_DETAIL_FIELDS,
    Contact,
    ContactCreate,
    ContactDetail,
    ContactPage,
    ContactPatch,
)
from psycopg import Connection, sql
from psycopg.errors import UniqueViolation
from write_security import require_json_write

from database import get_connection

router = APIRouter(prefix="/contacts", tags=["contacts"])

CONTACT_COLUMNS = (
    "id, first_name, last_name, email, status, can_login, "
    "date_of_birth, preferred_name, phonetic_name, pronouns, gender"
)


@router.get("", response_model=ContactPage)
def get_contacts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> ContactPage:
    """Return one page of contacts in stable name order."""
    offset = (page - 1) * page_size

    where_clause = ""
    parameters: list[Any] = []
    # Only this fixed fragment is interpolated; every value remains a DB parameter.
    scope = authorization.scope("contact:view")
    if not scope.unrestricted:
        where_clause = "WHERE id = ANY(%s)"
        parameters.append(list(scope.ids))
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


@router.get(
    "/{contact_id}",
    response_model=ContactDetail,
    responses={
        200: {
            "headers": {
                "ETag": {
                    "description": "Strong version tag required for PATCH",
                    "schema": {"type": "string"},
                }
            }
        }
    },
)
def get_contact(
    contact_id: UUID,
    response: Response,
    authorization: AuthorizationService = Depends(get_authorization_service),
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

    if row is None or (not authorization.allows("contact:view", contact_id)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )

    return contact_response(row, response)


def contact_response(row: dict[str, Any], response: Response) -> ContactDetail:
    contact = ContactDetail.model_validate(row)
    response.headers["ETag"] = contact_etag(contact)
    return contact


def contact_etag(contact: ContactDetail) -> str:
    return '"' + hashlib.sha256(contact.model_dump_json().encode()).hexdigest() + '"'


WRITE_ERRORS = {
    401: {"description": "Authentication required"},
    403: {"description": "Write permission or CSRF validation failed"},
    409: {"description": "Email is already assigned to a contact"},
    415: {"description": "Content-Type must be application/json"},
}
ETAG_HEADER = {
    "description": "Opaque strong version tag for If-Match",
    "schema": {"type": "string"},
}


@router.post(
    "",
    response_model=ContactDetail,
    status_code=201,
    dependencies=[Depends(require_json_write)],
    responses={
        **WRITE_ERRORS,
        201: {
            "headers": {
                "ETag": ETAG_HEADER,
                "Location": {
                    "description": "Relative contact detail URL",
                    "schema": {"type": "string"},
                },
            }
        },
    },
)
def create_contact(
    payload: ContactCreate,
    request: Request,
    response: Response,
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> ContactDetail:
    """Create a contact without creating an account or granting login access."""
    authorization.require("contact:create")
    try:
        row = connection.execute(
            f"""
            INSERT INTO contacts (first_name, last_name, email, status)
            VALUES (%s, %s, %s, %s)
            RETURNING {CONTACT_COLUMNS}, created_at, modified_at
            """,
            (
                payload.first_name,
                payload.last_name,
                payload.email,
                payload.status.value,
            ),
        ).fetchone()
    except UniqueViolation as error:
        raise HTTPException(
            status_code=409, detail="Email is already assigned to a contact"
        ) from error
    audit_event(
        connection,
        request,
        "contact.created",
        "success",
        account_id=authorization.user.account_id,
        details={"contact_id": str(row["id"])},
    )
    response.headers["Location"] = f"/api/v1/contacts/{row['id']}"
    return contact_response(row, response)


@router.patch(
    "/{contact_id}",
    response_model=ContactDetail,
    dependencies=[Depends(require_json_write)],
    responses={
        **WRITE_ERRORS,
        404: {"description": "Contact not found"},
        412: {"description": "Contact changed; refetch before retrying"},
        428: {"description": "If-Match is required"},
        200: {"headers": {"ETag": ETAG_HEADER}},
    },
)
def update_contact(
    contact_id: UUID,
    payload: ContactPatch,
    request: Request,
    response: Response,
    if_match: str | None = Header(
        default=None,
        description="One quoted strong ETag from the contact's GET or last write. Required; missing returns 428.",
    ),
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> ContactDetail:
    """Change supplied fields atomically.

    Which permission(s) are required depends on which fields the payload
    sets: contact:update for any of first_name/last_name/email/status,
    contact-personal:update for any of date_of_birth/preferred_name/
    phonetic_name/pronouns/gender (documents/api-contract.md "Personal
    details"). Both may be required in one request; if either fails, the
    whole request is rejected before anything is looked up or changed.
    email and the five personal-detail fields can be explicitly null;
    first_name, last_name, and status cannot. Archiving revokes existing
    sessions. Login identities are never edited.
    """
    # Deliberately check permission before looking up the target or its email.
    fields_present = payload.model_fields_set
    if fields_present & CORE_CONTACT_FIELDS:
        authorization.require("contact:update", contact_id)
    if fields_present & PERSONAL_DETAIL_FIELDS:
        authorization.require("contact-personal:update", contact_id)
    if if_match is None:
        raise HTTPException(status_code=428, detail="If-Match is required")
    if not re.fullmatch(r'"[!#-~]+"', if_match) or "," in if_match:
        raise HTTPException(status_code=422, detail="If-Match must be one strong ETag")
    current = connection.execute(
        f"SELECT {CONTACT_COLUMNS}, created_at, modified_at FROM contacts WHERE id = %s FOR UPDATE",
        (contact_id,),
    ).fetchone()
    if current is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    if if_match != contact_etag(ContactDetail.model_validate(current)):
        raise HTTPException(
            status_code=412, detail="Contact has changed; fetch it before retrying"
        )
    changes = payload.model_dump(exclude_unset=True, mode="json")
    # Column identifiers come only from the extra-forbid input model; values stay bound.
    assignments = sql.SQL(", ").join(
        sql.SQL("{} = %s").format(sql.Identifier(field)) for field in changes
    )
    try:
        row = connection.execute(
            sql.SQL(
                "UPDATE contacts SET {} WHERE id = %s RETURNING "
                + CONTACT_COLUMNS
                + ", created_at, modified_at"
            ).format(assignments),
            (*changes.values(), contact_id),
        ).fetchone()
    except UniqueViolation as error:
        raise HTTPException(
            status_code=409, detail="Email is already assigned to a contact"
        ) from error
    if changes.get("status") == "archived":
        connection.execute(
            """UPDATE user_sessions SET revoked_at = now()
               WHERE user_account_id IN (SELECT id FROM user_accounts WHERE contact_id = %s)
                 AND revoked_at IS NULL""",
            (contact_id,),
        )
    audit_event(
        connection,
        request,
        "contact.updated",
        "success",
        account_id=authorization.user.account_id,
        details={"contact_id": str(contact_id), "fields": sorted(changes)},
    )
    return contact_response(row, response)

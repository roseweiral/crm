"""Contact phone number and address reads and writes.

See documents/api-contract.md "Contact details: phone numbers and
addresses" for the full behavioral contract, including the write-access
model (self, the family's current Main Contact, and a Group Leader over
their exact group and its members' families).
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
from pydantic import BaseModel

from authentication import audit_event
from authorization import AuthorizationService, get_authorization_service
from database import get_connection
from models.contact_details import (
    ContactAddress,
    ContactAddressCreate,
    ContactAddressDetail,
    ContactAddressPage,
    ContactAddressPatch,
    ContactPhoneNumber,
    ContactPhoneNumberCreate,
    ContactPhoneNumberDetail,
    ContactPhoneNumberPage,
    ContactPhoneNumberPatch,
)
from write_security import require_json_write

router = APIRouter(tags=["contact details"])

PHONE_COLUMNS = "id, contact_id, phone_type, number, is_primary, start_date, end_date"
ADDRESS_COLUMNS = (
    "id, contact_id, address_type, line1, line2, city, region, postcode, "
    "country, start_date, end_date"
)

WRITE_ERRORS = {
    401: {"description": "Authentication required"},
    403: {"description": "Write permission or CSRF validation failed"},
    415: {"description": "Content-Type must be application/json"},
}
ETAG_HEADER = {
    "description": "Opaque strong version tag for If-Match",
    "schema": {"type": "string"},
}


def _etag(model: BaseModel) -> str:
    return '"' + hashlib.sha256(model.model_dump_json().encode()).hexdigest() + '"'


def _check_if_match(if_match: str | None) -> None:
    if if_match is None:
        raise HTTPException(status_code=428, detail="If-Match is required")
    if not re.fullmatch(r'"[!#-~]+"', if_match) or "," in if_match:
        raise HTTPException(status_code=422, detail="If-Match must be one strong ETag")


def _list_where(
    authorization: AuthorizationService, contact_id: UUID | None
) -> tuple[str, list[Any]]:
    scope = authorization.scope("contact:view")
    conditions = []
    parameters: list[Any] = []
    if not scope.unrestricted:
        conditions.append("contact_id = ANY(%s)")
        parameters.append(list(scope.ids))
    if contact_id is not None:
        conditions.append("contact_id = %s")
        parameters.append(contact_id)
    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    return where_clause, parameters


# --- Phone numbers -----------------------------------------------------------


def _phone_response(row: dict[str, Any], response: Response) -> ContactPhoneNumberDetail:
    phone = ContactPhoneNumberDetail.model_validate(row)
    response.headers["ETag"] = _etag(phone)
    return phone


@router.get("/contact-phone-numbers", response_model=ContactPhoneNumberPage)
def get_contact_phone_numbers(
    contact_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> ContactPhoneNumberPage:
    """Return one page of phone numbers, optionally filtered by contact_id."""
    offset = (page - 1) * page_size
    where_clause, parameters = _list_where(authorization, contact_id)
    total = connection.execute(
        f"SELECT count(*) AS total FROM contact_phone_numbers {where_clause}", parameters
    ).fetchone()["total"]
    rows = connection.execute(
        f"""
        SELECT {PHONE_COLUMNS}
        FROM contact_phone_numbers
        {where_clause}
        ORDER BY start_date DESC, id
        LIMIT %s OFFSET %s
        """,
        (*parameters, page_size, offset),
    ).fetchall()

    return ContactPhoneNumberPage(
        items=[ContactPhoneNumber.model_validate(row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/contact-phone-numbers/{phone_number_id}",
    response_model=ContactPhoneNumberDetail,
    responses={200: {"headers": {"ETag": ETAG_HEADER}}},
)
def get_contact_phone_number(
    phone_number_id: UUID,
    response: Response,
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> ContactPhoneNumberDetail:
    """Return a phone number by UUID."""
    row = connection.execute(
        f"SELECT {PHONE_COLUMNS}, created_at, modified_at FROM contact_phone_numbers WHERE id = %s",
        (phone_number_id,),
    ).fetchone()

    if row is None or not authorization.allows("contact:view", row["contact_id"]):
        raise HTTPException(status_code=404, detail="Phone number not found")

    return _phone_response(row, response)


@router.post(
    "/contact-phone-numbers",
    response_model=ContactPhoneNumberDetail,
    status_code=201,
    dependencies=[Depends(require_json_write)],
    responses={
        **WRITE_ERRORS,
        201: {
            "headers": {
                "ETag": ETAG_HEADER,
                "Location": {
                    "description": "Relative phone number detail URL",
                    "schema": {"type": "string"},
                },
            }
        },
    },
)
def create_contact_phone_number(
    payload: ContactPhoneNumberCreate,
    request: Request,
    response: Response,
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> ContactPhoneNumberDetail:
    """Create a phone number, atomically unsetting any prior primary."""
    authorization.require("contact-phone:update", payload.contact_id)
    if payload.is_primary:
        connection.execute("SELECT id FROM contacts WHERE id = %s FOR UPDATE", (payload.contact_id,))
        connection.execute(
            """UPDATE contact_phone_numbers SET is_primary = false
               WHERE contact_id = %s AND is_primary AND end_date IS NULL""",
            (payload.contact_id,),
        )
    row = connection.execute(
        f"""
        INSERT INTO contact_phone_numbers (contact_id, phone_type, number, is_primary)
        VALUES (%s, %s, %s, %s)
        RETURNING {PHONE_COLUMNS}, created_at, modified_at
        """,
        (payload.contact_id, payload.phone_type.value, payload.number, payload.is_primary),
    ).fetchone()
    audit_event(
        connection,
        request,
        "contact_phone_number.created",
        "success",
        account_id=authorization.user.account_id,
        details={"contact_phone_number_id": str(row["id"]), "contact_id": str(payload.contact_id)},
    )
    response.headers["Location"] = f"/api/v1/contact-phone-numbers/{row['id']}"
    return _phone_response(row, response)


@router.patch(
    "/contact-phone-numbers/{phone_number_id}",
    response_model=ContactPhoneNumberDetail,
    dependencies=[Depends(require_json_write)],
    responses={
        **WRITE_ERRORS,
        404: {"description": "Phone number not found"},
        412: {"description": "Phone number changed; refetch before retrying"},
        428: {"description": "If-Match is required"},
        200: {"headers": {"ETag": ETAG_HEADER}},
    },
)
def update_contact_phone_number(
    phone_number_id: UUID,
    payload: ContactPhoneNumberPatch,
    request: Request,
    response: Response,
    if_match: str | None = Header(
        default=None,
        description="One quoted strong ETag from the phone number's GET or last write. Required; missing returns 428.",
    ),
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> ContactPhoneNumberDetail:
    """Change supplied fields atomically; setting end_date retires the number."""
    current = connection.execute(
        f"SELECT {PHONE_COLUMNS}, created_at, modified_at FROM contact_phone_numbers WHERE id = %s FOR UPDATE",
        (phone_number_id,),
    ).fetchone()
    if current is None:
        raise HTTPException(status_code=404, detail="Phone number not found")
    authorization.require("contact-phone:update", current["contact_id"])
    _check_if_match(if_match)
    if if_match != _etag(ContactPhoneNumberDetail.model_validate(current)):
        raise HTTPException(
            status_code=412, detail="Phone number has changed; fetch it before retrying"
        )
    changes = payload.model_dump(exclude_unset=True, mode="json")
    if changes.get("is_primary") is True:
        connection.execute(
            """UPDATE contact_phone_numbers SET is_primary = false
               WHERE contact_id = %s AND is_primary AND end_date IS NULL AND id <> %s""",
            (current["contact_id"], phone_number_id),
        )
    assignments = sql.SQL(", ").join(
        sql.SQL("{} = %s").format(sql.Identifier(field)) for field in changes
    )
    row = connection.execute(
        sql.SQL(
            "UPDATE contact_phone_numbers SET {} WHERE id = %s RETURNING "
            + PHONE_COLUMNS
            + ", created_at, modified_at"
        ).format(assignments),
        (*changes.values(), phone_number_id),
    ).fetchone()
    audit_event(
        connection,
        request,
        "contact_phone_number.updated",
        "success",
        account_id=authorization.user.account_id,
        details={
            "contact_phone_number_id": str(phone_number_id),
            "contact_id": str(current["contact_id"]),
            "fields": sorted(changes),
        },
    )
    return _phone_response(row, response)


# --- Addresses -----------------------------------------------------------


def _address_response(row: dict[str, Any], response: Response) -> ContactAddressDetail:
    address = ContactAddressDetail.model_validate(row)
    response.headers["ETag"] = _etag(address)
    return address


@router.get("/contact-addresses", response_model=ContactAddressPage)
def get_contact_addresses(
    contact_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> ContactAddressPage:
    """Return one page of addresses, optionally filtered by contact_id."""
    offset = (page - 1) * page_size
    where_clause, parameters = _list_where(authorization, contact_id)
    total = connection.execute(
        f"SELECT count(*) AS total FROM contact_addresses {where_clause}", parameters
    ).fetchone()["total"]
    rows = connection.execute(
        f"""
        SELECT {ADDRESS_COLUMNS}
        FROM contact_addresses
        {where_clause}
        ORDER BY start_date DESC, id
        LIMIT %s OFFSET %s
        """,
        (*parameters, page_size, offset),
    ).fetchall()

    return ContactAddressPage(
        items=[ContactAddress.model_validate(row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/contact-addresses/{address_id}",
    response_model=ContactAddressDetail,
    responses={200: {"headers": {"ETag": ETAG_HEADER}}},
)
def get_contact_address(
    address_id: UUID,
    response: Response,
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> ContactAddressDetail:
    """Return an address by UUID."""
    row = connection.execute(
        f"SELECT {ADDRESS_COLUMNS}, created_at, modified_at FROM contact_addresses WHERE id = %s",
        (address_id,),
    ).fetchone()

    if row is None or not authorization.allows("contact:view", row["contact_id"]):
        raise HTTPException(status_code=404, detail="Address not found")

    return _address_response(row, response)


@router.post(
    "/contact-addresses",
    response_model=ContactAddressDetail,
    status_code=201,
    dependencies=[Depends(require_json_write)],
    responses={
        **WRITE_ERRORS,
        201: {
            "headers": {
                "ETag": ETAG_HEADER,
                "Location": {
                    "description": "Relative address detail URL",
                    "schema": {"type": "string"},
                },
            }
        },
    },
)
def create_contact_address(
    payload: ContactAddressCreate,
    request: Request,
    response: Response,
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> ContactAddressDetail:
    """Create an address."""
    authorization.require("contact-address:update", payload.contact_id)
    row = connection.execute(
        f"""
        INSERT INTO contact_addresses
          (contact_id, address_type, line1, line2, city, region, postcode, country)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING {ADDRESS_COLUMNS}, created_at, modified_at
        """,
        (
            payload.contact_id,
            payload.address_type.value,
            payload.line1,
            payload.line2,
            payload.city,
            payload.region,
            payload.postcode,
            payload.country,
        ),
    ).fetchone()
    audit_event(
        connection,
        request,
        "contact_address.created",
        "success",
        account_id=authorization.user.account_id,
        details={"contact_address_id": str(row["id"]), "contact_id": str(payload.contact_id)},
    )
    response.headers["Location"] = f"/api/v1/contact-addresses/{row['id']}"
    return _address_response(row, response)


@router.patch(
    "/contact-addresses/{address_id}",
    response_model=ContactAddressDetail,
    dependencies=[Depends(require_json_write)],
    responses={
        **WRITE_ERRORS,
        404: {"description": "Address not found"},
        412: {"description": "Address changed; refetch before retrying"},
        428: {"description": "If-Match is required"},
        200: {"headers": {"ETag": ETAG_HEADER}},
    },
)
def update_contact_address(
    address_id: UUID,
    payload: ContactAddressPatch,
    request: Request,
    response: Response,
    if_match: str | None = Header(
        default=None,
        description="One quoted strong ETag from the address's GET or last write. Required; missing returns 428.",
    ),
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> ContactAddressDetail:
    """Change supplied fields atomically; setting end_date retires the address."""
    current = connection.execute(
        f"SELECT {ADDRESS_COLUMNS}, created_at, modified_at FROM contact_addresses WHERE id = %s FOR UPDATE",
        (address_id,),
    ).fetchone()
    if current is None:
        raise HTTPException(status_code=404, detail="Address not found")
    authorization.require("contact-address:update", current["contact_id"])
    _check_if_match(if_match)
    if if_match != _etag(ContactAddressDetail.model_validate(current)):
        raise HTTPException(
            status_code=412, detail="Address has changed; fetch it before retrying"
        )
    changes = payload.model_dump(exclude_unset=True, mode="json")
    assignments = sql.SQL(", ").join(
        sql.SQL("{} = %s").format(sql.Identifier(field)) for field in changes
    )
    row = connection.execute(
        sql.SQL(
            "UPDATE contact_addresses SET {} WHERE id = %s RETURNING "
            + ADDRESS_COLUMNS
            + ", created_at, modified_at"
        ).format(assignments),
        (*changes.values(), address_id),
    ).fetchone()
    audit_event(
        connection,
        request,
        "contact_address.updated",
        "success",
        account_id=authorization.user.account_id,
        details={
            "contact_address_id": str(address_id),
            "contact_id": str(current["contact_id"]),
            "fields": sorted(changes),
        },
    )
    return _address_response(row, response)

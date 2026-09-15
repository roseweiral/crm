"""Organisation-wide address book: directory reads and self-service visibility.

See documents/api-contract.md "Organisation-wide address book" for the full
contract and documents/family-and-directory-design.md for the eligibility
rationale.
"""

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
from models.address_book import (
    AddressBookEntry,
    AddressBookPage,
    DirectoryVisibility,
    DirectoryVisibilityPatch,
)
from psycopg import Connection
from write_security import require_json_write

from database import get_connection

router = APIRouter(prefix="/address-book", tags=["address book"])

# Young Member is deliberately excluded: a role type linking a child to a
# group must never make that child (or, by itself, an adult) a directory
# entry. Only these organisational roles, or an is_global access role
# (handled separately), make an adult eligible.
ELIGIBLE_GROUP_ROLE_TYPES = ("Group Leader", "Group Helper", "Area Manager")

DIRECTORY_CANDIDATES_CTE = """
WITH directory_group_roles AS (
    SELECT DISTINCT crg.contact_id
    FROM contact_roles_groups crg
    JOIN role_types rt ON rt.id = crg.role_type_id
    WHERE rt.name = ANY(%s)
      AND crg.hidden_from_directory = false
      AND crg.start_date <= current_date
      AND (crg.end_date IS NULL OR crg.end_date >= current_date)
),
directory_access_roles AS (
    SELECT DISTINCT ua.contact_id
    FROM user_access_role_assignments uara
    JOIN user_accounts ua ON ua.id = uara.user_account_id
    JOIN access_roles ar ON ar.id = uara.access_role_id
    WHERE ar.is_global = true
      AND uara.hidden_from_directory = false
      AND uara.start_date <= current_date
      AND (uara.end_date IS NULL OR uara.end_date >= current_date)
),
directory_candidates AS (
    SELECT contact_id FROM directory_group_roles
    UNION
    SELECT contact_id FROM directory_access_roles
)
"""


def _group_paths(connection: Connection[Any], group_ids: set[UUID]) -> dict[UUID, list[dict[str, Any]]]:
    """Root-to-leaf ancestor chain (inclusive) for each of the given groups."""
    if not group_ids:
        return {}
    rows = connection.execute(
        """
        WITH RECURSIVE ancestry(leaf_id, id, name, parent_id, depth) AS (
            SELECT g.id, g.id, g.name, g.parent_id, 0
            FROM groups g
            WHERE g.id = ANY(%s)
            UNION ALL
            SELECT ancestry.leaf_id, p.id, p.name, p.parent_id, ancestry.depth + 1
            FROM groups p
            JOIN ancestry ON ancestry.parent_id = p.id
        )
        SELECT leaf_id, id, name FROM ancestry ORDER BY leaf_id, depth DESC
        """,
        (list(group_ids),),
    ).fetchall()
    paths: dict[UUID, list[dict[str, Any]]] = {}
    for row in rows:
        paths.setdefault(row["leaf_id"], []).append({"id": row["id"], "name": row["name"]})
    return paths


def _load_directory_roles(connection: Connection[Any], contact_ids: list[UUID]) -> dict[UUID, list[dict[str, Any]]]:
    """Visible eligible roles for each contact, keyed by contact_id."""
    if not contact_ids:
        return {}
    group_rows = connection.execute(
        """
        SELECT crg.contact_id, rt.name AS role_type_name, crg.group_id, g.name AS group_name
        FROM contact_roles_groups crg
        JOIN role_types rt ON rt.id = crg.role_type_id
        JOIN groups g ON g.id = crg.group_id
        WHERE crg.contact_id = ANY(%s)
          AND rt.name = ANY(%s)
          AND crg.hidden_from_directory = false
          AND crg.start_date <= current_date
          AND (crg.end_date IS NULL OR crg.end_date >= current_date)
        ORDER BY crg.start_date, crg.id
        """,
        (contact_ids, list(ELIGIBLE_GROUP_ROLE_TYPES)),
    ).fetchall()
    access_rows = connection.execute(
        """
        SELECT ua.contact_id, ar.name AS access_role_name
        FROM user_access_role_assignments uara
        JOIN user_accounts ua ON ua.id = uara.user_account_id
        JOIN access_roles ar ON ar.id = uara.access_role_id
        WHERE ua.contact_id = ANY(%s)
          AND ar.is_global = true
          AND uara.hidden_from_directory = false
          AND uara.start_date <= current_date
          AND (uara.end_date IS NULL OR uara.end_date >= current_date)
        ORDER BY uara.start_date, uara.id
        """,
        (contact_ids,),
    ).fetchall()

    paths = _group_paths(connection, {row["group_id"] for row in group_rows})
    roles: dict[UUID, list[dict[str, Any]]] = {contact_id: [] for contact_id in contact_ids}
    for row in group_rows:
        roles[row["contact_id"]].append(
            {
                "kind": "group_role",
                "role_type_name": row["role_type_name"],
                "group_id": row["group_id"],
                "group_name": row["group_name"],
                "group_path": paths.get(
                    row["group_id"], [{"id": row["group_id"], "name": row["group_name"]}]
                ),
            }
        )
    for row in access_rows:
        roles[row["contact_id"]].append(
            {"kind": "access_role", "access_role_name": row["access_role_name"]}
        )
    return roles


def _entry(row: dict[str, Any], roles: list[dict[str, Any]]) -> AddressBookEntry:
    return AddressBookEntry(
        contact_id=row["id"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        email=row["email"],
        roles=roles,
    )


@router.get("", response_model=AddressBookPage)
def get_address_book(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> AddressBookPage:
    """Return one page of the address book, for eligible volunteers only."""
    authorization.require("directory:view")
    offset = (page - 1) * page_size
    rows = connection.execute(
        DIRECTORY_CANDIDATES_CTE
        + """
        SELECT c.id, c.first_name, c.last_name, c.email, count(*) OVER () AS total
        FROM contacts c
        JOIN directory_candidates dc ON dc.contact_id = c.id
        WHERE c.status = 'active' AND c.hidden_from_directory = false
        ORDER BY c.last_name, c.first_name, c.id
        LIMIT %s OFFSET %s
        """,
        (list(ELIGIBLE_GROUP_ROLE_TYPES), page_size, offset),
    ).fetchall()
    total = rows[0]["total"] if rows else 0
    roles_by_contact = _load_directory_roles(connection, [row["id"] for row in rows])
    return AddressBookPage(
        items=[_entry(row, roles_by_contact.get(row["id"], [])) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


# --- Self-service visibility (registered before {contact_id} so "visibility"
# is never matched as a contact UUID) ----------------------------------------


def _load_visibility(connection: Connection[Any], user: Any) -> DirectoryVisibility:
    contact_row = connection.execute(
        "SELECT hidden_from_directory FROM contacts WHERE id = %s",
        (user.contact_id,),
    ).fetchone()
    group_rows = connection.execute(
        """
        SELECT crg.id, rt.name AS role_type_name, g.name AS group_name, crg.hidden_from_directory
        FROM contact_roles_groups crg
        JOIN role_types rt ON rt.id = crg.role_type_id
        JOIN groups g ON g.id = crg.group_id
        WHERE crg.contact_id = %s
          AND rt.name = ANY(%s)
          AND crg.start_date <= current_date
          AND (crg.end_date IS NULL OR crg.end_date >= current_date)
        ORDER BY crg.start_date, crg.id
        """,
        (user.contact_id, list(ELIGIBLE_GROUP_ROLE_TYPES)),
    ).fetchall()
    access_rows = connection.execute(
        """
        SELECT uara.id, ar.name AS access_role_name, uara.hidden_from_directory
        FROM user_access_role_assignments uara
        JOIN access_roles ar ON ar.id = uara.access_role_id
        WHERE uara.user_account_id = %s
          AND ar.is_global = true
          AND uara.start_date <= current_date
          AND (uara.end_date IS NULL OR uara.end_date >= current_date)
        ORDER BY uara.start_date, uara.id
        """,
        (user.account_id,),
    ).fetchall()
    roles = [
        {
            "id": row["id"],
            "kind": "group_role",
            "role_type_name": row["role_type_name"],
            "group_name": row["group_name"],
            "hidden_from_directory": row["hidden_from_directory"],
        }
        for row in group_rows
    ] + [
        {
            "id": row["id"],
            "kind": "access_role",
            "access_role_name": row["access_role_name"],
            "hidden_from_directory": row["hidden_from_directory"],
        }
        for row in access_rows
    ]
    return DirectoryVisibility(hidden_from_directory=contact_row["hidden_from_directory"], roles=roles)


def _visibility_etag(payload: DirectoryVisibility) -> str:
    return '"' + hashlib.sha256(payload.model_dump_json().encode()).hexdigest() + '"'


VISIBILITY_ETAG_HEADER = {
    "description": "Opaque strong version tag for If-Match",
    "schema": {"type": "string"},
}


@router.get(
    "/visibility",
    response_model=DirectoryVisibility,
    responses={200: {"headers": {"ETag": VISIBILITY_ETAG_HEADER}}},
)
def get_directory_visibility(
    response: Response,
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> DirectoryVisibility:
    """Return the caller's own visibility settings, whether or not they are
    currently eligible for the directory."""
    authorization.require("directory-visibility:manage-own", authorization.user.contact_id)
    payload = _load_visibility(connection, authorization.user)
    response.headers["ETag"] = _visibility_etag(payload)
    return payload


@router.patch(
    "/visibility",
    response_model=DirectoryVisibility,
    dependencies=[Depends(require_json_write)],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "CSRF validation failed"},
        412: {"description": "Visibility settings changed; refetch before retrying"},
        415: {"description": "Content-Type must be application/json"},
        422: {"description": "Malformed If-Match, empty patch, or unknown role id"},
        428: {"description": "If-Match is required"},
        200: {"headers": {"ETag": VISIBILITY_ETAG_HEADER}},
    },
)
def update_directory_visibility(
    payload: DirectoryVisibilityPatch,
    request: Request,
    response: Response,
    if_match: str | None = Header(
        default=None,
        description="One quoted strong ETag from the last GET or write. Required; missing returns 428.",
    ),
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> DirectoryVisibility:
    """Change the caller's own visibility settings atomically."""
    authorization.require("directory-visibility:manage-own", authorization.user.contact_id)
    if if_match is None:
        raise HTTPException(status_code=428, detail="If-Match is required")
    if not re.fullmatch(r'"[!#-~]+"', if_match) or "," in if_match:
        raise HTTPException(status_code=422, detail="If-Match must be one strong ETag")

    # Lock the contact row for the duration of the check-then-write.
    connection.execute(
        "SELECT id FROM contacts WHERE id = %s FOR UPDATE", (authorization.user.contact_id,)
    )
    current = _load_visibility(connection, authorization.user)
    if if_match != _visibility_etag(current):
        raise HTTPException(
            status_code=412, detail="Visibility settings have changed; fetch them before retrying"
        )

    changes = payload.model_dump(exclude_unset=True, mode="json")
    changed_role_ids: list[str] = []

    if "hidden_from_directory" in changes:
        connection.execute(
            "UPDATE contacts SET hidden_from_directory = %s WHERE id = %s",
            (changes["hidden_from_directory"], authorization.user.contact_id),
        )

    if "roles" in changes:
        role_patches = {UUID(item["id"]): item["hidden_from_directory"] for item in changes["roles"]}
        role_ids = list(role_patches)
        # Ownership alone isn't enough: only a *current, eligible* assignment
        # may be patched, matching the set GET already returns (see
        # _load_visibility) and documents/api-contract.md's "current eligible
        # assignments" rule. An ended or ineligible-role-type id the caller
        # still owns must be rejected exactly like a foreign id.
        owned_group_role_ids = {
            row["id"]
            for row in connection.execute(
                """
                SELECT crg.id
                FROM contact_roles_groups crg
                JOIN role_types rt ON rt.id = crg.role_type_id
                WHERE crg.id = ANY(%s) AND crg.contact_id = %s
                  AND rt.name = ANY(%s)
                  AND crg.start_date <= current_date
                  AND (crg.end_date IS NULL OR crg.end_date >= current_date)
                """,
                (role_ids, authorization.user.contact_id, list(ELIGIBLE_GROUP_ROLE_TYPES)),
            ).fetchall()
        }
        owned_access_role_ids = {
            row["id"]
            for row in connection.execute(
                """
                SELECT uara.id
                FROM user_access_role_assignments uara
                JOIN access_roles ar ON ar.id = uara.access_role_id
                WHERE uara.id = ANY(%s) AND uara.user_account_id = %s
                  AND ar.is_global = true
                  AND uara.start_date <= current_date
                  AND (uara.end_date IS NULL OR uara.end_date >= current_date)
                """,
                (role_ids, authorization.user.account_id),
            ).fetchall()
        }
        unknown = set(role_patches) - owned_group_role_ids - owned_access_role_ids
        if unknown:
            raise HTTPException(
                status_code=422, detail="One or more role IDs are not your own current eligible roles"
            )
        for role_id, hidden in role_patches.items():
            table = "contact_roles_groups" if role_id in owned_group_role_ids else "user_access_role_assignments"
            connection.execute(
                f"UPDATE {table} SET hidden_from_directory = %s WHERE id = %s",  # noqa: S608 - table is one of two fixed literals
                (hidden, role_id),
            )
            changed_role_ids.append(str(role_id))

    audit_event(
        connection,
        request,
        "directory_visibility.updated",
        "success",
        account_id=authorization.user.account_id,
        details={"fields": sorted(set(changes) - {"roles"}), "role_ids": changed_role_ids},
    )
    updated = _load_visibility(connection, authorization.user)
    response.headers["ETag"] = _visibility_etag(updated)
    return updated


# --- Directory detail (registered after "/visibility") ----------------------


@router.get(
    "/{contact_id}",
    response_model=AddressBookEntry,
    responses={404: {"description": "Address book entry not found"}},
)
def get_address_book_entry(
    contact_id: UUID,
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> AddressBookEntry:
    """Return one directory entry, or 404 if the caller is ineligible, the
    contact does not exist, or the contact is not currently a directory entry.
    """
    authorization.require("directory:view")
    row = connection.execute(
        DIRECTORY_CANDIDATES_CTE
        + """
        SELECT c.id, c.first_name, c.last_name, c.email
        FROM contacts c
        JOIN directory_candidates dc ON dc.contact_id = c.id
        WHERE c.status = 'active' AND c.hidden_from_directory = false AND c.id = %s
        """,
        (list(ELIGIBLE_GROUP_ROLE_TYPES), contact_id),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Address book entry not found"
        )
    roles = _load_directory_roles(connection, [row["id"]]).get(row["id"], [])
    return _entry(row, roles)

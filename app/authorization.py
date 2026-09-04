"""Request-scoped authorization derived from accounts, roles, groups, and families."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import Depends
from psycopg import Connection

from authentication import CurrentUser, get_current_user
from database import get_connection


@dataclass(frozen=True)
class AuthorizationScope:
    user: CurrentUser
    is_global_administrator: bool
    group_ids: frozenset[UUID]
    contact_ids: frozenset[UUID]
    family_unit_ids: frozenset[UUID]


def get_authorization_scope(
    user: CurrentUser = Depends(get_current_user),
    connection: Connection[Any] = Depends(get_connection),
) -> AuthorizationScope:
    is_global = connection.execute(
        """
        SELECT EXISTS (
          SELECT 1
          FROM user_access_role_assignments uara
          JOIN access_roles ar ON ar.id = uara.access_role_id
          WHERE uara.user_account_id = %s
            AND ar.is_global
            AND uara.start_date <= current_date
            AND (uara.end_date IS NULL OR uara.end_date >= current_date)
        ) AS allowed
        """,
        (user.account_id,),
    ).fetchone()["allowed"]
    if is_global:
        return AuthorizationScope(
            user=user,
            is_global_administrator=True,
            group_ids=frozenset(),
            contact_ids=frozenset(),
            family_unit_ids=frozenset(),
        )

    group_rows = connection.execute(
        """
        WITH RECURSIVE managed_groups AS (
          SELECT crg.group_id AS id
          FROM contact_roles_groups crg
          JOIN role_types rt ON rt.id = crg.role_type_id
          WHERE crg.contact_id = %s
            AND rt.name IN ('Group Leader', 'Area Manager')
            AND crg.start_date <= current_date
            AND (crg.end_date IS NULL OR crg.end_date >= current_date)
          UNION
          SELECT g.id
          FROM groups g
          JOIN managed_groups parent ON parent.id = g.parent_id
        )
        SELECT id FROM managed_groups
        """,
        (user.contact_id,),
    ).fetchall()
    group_ids = frozenset(row["id"] for row in group_rows)

    contact_ids: set[UUID] = {user.contact_id}
    if group_ids:
        rows = connection.execute(
            """
            SELECT DISTINCT contact_id
            FROM contact_roles_groups
            WHERE group_id = ANY(%s)
              AND start_date <= current_date
              AND (end_date IS NULL OR end_date >= current_date)
            """,
            (list(group_ids),),
        ).fetchall()
        contact_ids.update(row["contact_id"] for row in rows)

    parent_families = connection.execute(
        """
        SELECT family_unit_id
        FROM contact_family_units
        WHERE contact_id = %s AND relationship = 'parent'
        """,
        (user.contact_id,),
    ).fetchall()
    family_ids = frozenset(row["family_unit_id"] for row in parent_families)
    if family_ids:
        rows = connection.execute(
            """
            SELECT DISTINCT contact_id
            FROM contact_family_units
            WHERE family_unit_id = ANY(%s)
            """,
            (list(family_ids),),
        ).fetchall()
        contact_ids.update(row["contact_id"] for row in rows)

    return AuthorizationScope(
        user=user,
        is_global_administrator=False,
        group_ids=group_ids,
        contact_ids=frozenset(contact_ids),
        family_unit_ids=family_ids,
    )

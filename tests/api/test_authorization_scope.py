"""Regression tests for descendant-group authorization boundaries."""

import hashlib
import secrets

import httpx
import psycopg
import pytest
from psycopg.rows import dict_row

from .support import API_URL, DATABASE_URL


pytestmark = pytest.mark.regression


def test_group_leader_sees_descendants_but_not_other_branches() -> None:
    raw_session = secrets.token_urlsafe(48)
    created_account = False
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        leader = connection.execute(
            """
            SELECT crg.contact_id, crg.group_id
            FROM contact_roles_groups crg
            JOIN role_types rt ON rt.id = crg.role_type_id
            LEFT JOIN user_accounts ua ON ua.contact_id = crg.contact_id
            WHERE rt.name = 'Group Leader'
              AND crg.end_date IS NULL
              AND NOT EXISTS (
                SELECT 1 FROM user_access_role_assignments a
                JOIN access_roles ar ON ar.id = a.access_role_id
                WHERE a.user_account_id = ua.id AND ar.is_global
              )
            ORDER BY crg.id
            LIMIT 1
            """
        ).fetchone()
        account = connection.execute(
            "SELECT id FROM user_accounts WHERE contact_id = %s",
            (leader["contact_id"],),
        ).fetchone()
        if account is None:
            account = connection.execute(
                "INSERT INTO user_accounts (contact_id, status) VALUES (%s, 'active') RETURNING id",
                (leader["contact_id"],),
            ).fetchone()
            created_account = True
        session_id = connection.execute(
            "INSERT INTO user_sessions (user_account_id, token_hash) VALUES (%s, %s) RETURNING id",
            (account["id"], hashlib.sha256(raw_session.encode()).hexdigest()),
        ).fetchone()["id"]
        expected_groups = {
            row["id"]
            for row in connection.execute(
                """
                WITH RECURSIVE descendants AS (
                  SELECT id FROM groups WHERE id = %s
                  UNION ALL
                  SELECT g.id FROM groups g JOIN descendants d ON d.id = g.parent_id
                ) SELECT id FROM descendants
                """,
                (leader["group_id"],),
            ).fetchall()
        }

    try:
        with httpx.Client(cookies={"crm_session": raw_session}) as client:
            response = client.get(f"{API_URL}/api/v1/groups", params={"page_size": 100})
        assert response.status_code == 200
        actual_groups = {item["id"] for item in response.json()["items"]}
        assert actual_groups == {str(group_id) for group_id in expected_groups}
    finally:
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute("DELETE FROM user_sessions WHERE id = %s", (session_id,))
            if created_account:
                connection.execute("DELETE FROM user_accounts WHERE id = %s", (account["id"],))

"""Regression tests for descendant-group authorization boundaries."""

import hashlib
import secrets
from contextlib import contextmanager
from collections.abc import Iterator
from uuid import UUID

import httpx
import psycopg
import pytest
from psycopg.rows import dict_row

from .support import API_URL, DATABASE_URL


pytestmark = pytest.mark.regression


@contextmanager
def session_for_contact(contact_id: UUID) -> Iterator[str]:
    raw_session = secrets.token_urlsafe(48)
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        account_id = connection.execute(
            "SELECT id FROM user_accounts WHERE contact_id = %s", (contact_id,)
        ).fetchone()["id"]
        session_id = connection.execute(
            "INSERT INTO user_sessions (user_account_id, token_hash) VALUES (%s, %s) RETURNING id",
            (account_id, hashlib.sha256(raw_session.encode()).hexdigest()),
        ).fetchone()["id"]
    try:
        yield raw_session
    finally:
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute("DELETE FROM user_sessions WHERE id = %s", (session_id,))


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


def test_parent_sees_their_family_but_not_unrelated_contacts() -> None:
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        parent = connection.execute(
            """
            SELECT cfu.contact_id, cfu.family_unit_id
            FROM contact_family_units cfu
            WHERE cfu.relationship = 'parent'
              AND NOT EXISTS (
                SELECT 1 FROM user_access_role_assignments assignment
                JOIN user_accounts ua ON ua.id = assignment.user_account_id
                WHERE ua.contact_id = cfu.contact_id
              )
            LIMIT 1
            """
        ).fetchone()
        family_contacts = {
            str(row["contact_id"])
            for row in connection.execute(
                "SELECT contact_id FROM contact_family_units WHERE family_unit_id = %s",
                (parent["family_unit_id"],),
            ).fetchall()
        }
        paused_roles = [
            row["id"]
            for row in connection.execute(
                "SELECT id FROM contact_roles_groups WHERE contact_id = %s AND end_date IS NULL",
                (parent["contact_id"],),
            ).fetchall()
        ]
        if paused_roles:
            connection.execute(
                "UPDATE contact_roles_groups SET end_date = current_date - 1 WHERE id = ANY(%s)",
                (paused_roles,),
            )

    try:
        with session_for_contact(parent["contact_id"]) as raw_session:
            with httpx.Client(cookies={"crm_session": raw_session}) as client:
                contacts = client.get(f"{API_URL}/api/v1/contacts", params={"page_size": 100})
                families = client.get(f"{API_URL}/api/v1/family-units", params={"page_size": 100})
    finally:
        if paused_roles:
            with psycopg.connect(DATABASE_URL) as connection:
                connection.execute(
                    "UPDATE contact_roles_groups SET end_date = NULL WHERE id = ANY(%s)",
                    (paused_roles,),
                )

    assert contacts.status_code == 200
    assert {item["id"] for item in contacts.json()["items"]} == family_contacts
    assert families.status_code == 200
    assert {item["id"] for item in families.json()["items"]} == {
        str(parent["family_unit_id"])
    }


def test_child_sees_only_their_own_contact_and_no_family_record() -> None:
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        child_id = connection.execute(
            """
            SELECT contact_id FROM contact_family_units
            WHERE relationship = 'child'
            LIMIT 1
            """
        ).fetchone()["contact_id"]

    with session_for_contact(child_id) as raw_session:
        with httpx.Client(cookies={"crm_session": raw_session}) as client:
            contacts = client.get(f"{API_URL}/api/v1/contacts", params={"page_size": 100})
            families = client.get(f"{API_URL}/api/v1/family-units", params={"page_size": 100})

    assert contacts.status_code == 200
    assert [item["id"] for item in contacts.json()["items"]] == [str(child_id)]
    assert families.status_code == 200
    assert families.json()["items"] == []

"""Database contracts for accounts, identities, invitations, and sessions."""

import csv
from datetime import timedelta
from pathlib import Path
from uuid import UUID

import psycopg
import pytest

from .support import DATABASE_URL, database_rows


pytestmark = pytest.mark.contract


def test_first_seed_contact_has_the_explicit_active_user_account() -> None:
    seed_directory = Path("/database/seed")
    with (seed_directory / "contacts.csv").open(encoding="utf-8") as contacts_file:
        first_contact = next(csv.DictReader(contacts_file))
    with (seed_directory / "user_accounts.csv").open(
        encoding="utf-8"
    ) as accounts_file:
        account = next(csv.DictReader(accounts_file))

    assert UUID(account["contact_id"]) == UUID(first_contact["id"])
    assert account["status"] == "active"


def test_every_demo_login_contact_has_an_account() -> None:
    contacts_without_accounts = database_rows(
        """
        SELECT c.id
        FROM contacts c
        LEFT JOIN user_accounts ua ON ua.contact_id = c.id
        WHERE c.can_login AND ua.id IS NULL
        """
    )

    assert contacts_without_accounts == []


def test_account_identity_and_secret_constraints() -> None:
    constraints = database_rows(
        """
        SELECT conname
        FROM pg_constraint
        WHERE conname IN (
          'user_accounts_contact_id_key',
          'user_identities_user_account_id_key',
          'uq_user_identities_issuer_subject',
          'invitations_token_hash_key',
          'chk_invitations_token_hash',
          'user_sessions_token_hash_key',
          'chk_user_sessions_token_hash'
        )
        """
    )

    assert {row["conname"] for row in constraints} == {
        "user_accounts_contact_id_key",
        "user_identities_user_account_id_key",
        "uq_user_identities_issuer_subject",
        "invitations_token_hash_key",
        "chk_invitations_token_hash",
        "user_sessions_token_hash_key",
        "chk_user_sessions_token_hash",
    }


def test_invitation_and_session_defaults_match_the_agreed_lifetimes() -> None:
    with psycopg.connect(DATABASE_URL) as connection:
        account_id = connection.execute(
            "SELECT id FROM user_accounts ORDER BY id LIMIT 1"
        ).fetchone()[0]
        invitation = connection.execute(
            """
            INSERT INTO invitations (user_account_id, email, token_hash)
            VALUES (%s, 'lifetime@example.test', %s)
            RETURNING created_at, expires_at
            """,
            (account_id, "a" * 64),
        ).fetchone()
        session = connection.execute(
            """
            INSERT INTO user_sessions (user_account_id, token_hash)
            VALUES (%s, %s)
            RETURNING created_at, expires_at
            """,
            (account_id, "b" * 64),
        ).fetchone()
        connection.rollback()

    assert invitation[1] - invitation[0] == timedelta(days=7)
    assert session[1] - session[0] == timedelta(hours=12)

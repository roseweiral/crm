"""Create the first Global System Administrator invitation."""

from __future__ import annotations

import argparse
import hashlib
import os
import secrets
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contact_id", type=UUID)
    args = parser.parse_args()
    database_url = os.environ["DATABASE_URL"]
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    raw_token = secrets.token_urlsafe(48)

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        if connection.execute(
            "SELECT EXISTS (SELECT 1 FROM user_access_role_assignments) AS exists"
        ).fetchone()["exists"]:
            raise SystemExit("Bootstrap refused: an access-role assignment already exists")
        contact = connection.execute(
            "SELECT email, status FROM contacts WHERE id = %s", (args.contact_id,)
        ).fetchone()
        if contact is None or contact["status"] == "archived" or not contact["email"]:
            raise SystemExit("Bootstrap contact must exist, be unarchived, and have an email")
        permission = connection.execute(
            """
            INSERT INTO permissions (name, description)
            VALUES ('crm.read', 'Read CRM information within the effective scope')
            ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description
            RETURNING id
            """
        ).fetchone()
        role = connection.execute(
            """
            INSERT INTO access_roles (name, description, is_global)
            VALUES ('Global System Administrator', 'Read all CRM information', true)
            ON CONFLICT (name) DO UPDATE SET is_global = true
            RETURNING id
            """
        ).fetchone()
        connection.execute(
            "INSERT INTO access_role_permissions VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (role["id"], permission["id"]),
        )
        account = connection.execute(
            "INSERT INTO user_accounts (contact_id, status) VALUES (%s, 'invited') RETURNING id",
            (args.contact_id,),
        ).fetchone()
        connection.execute(
            "INSERT INTO user_access_role_assignments (user_account_id, access_role_id) VALUES (%s, %s)",
            (account["id"], role["id"]),
        )
        connection.execute(
            "INSERT INTO invitations (user_account_id, email, token_hash) VALUES (%s, %s, %s)",
            (account["id"], contact["email"].lower(), hashlib.sha256(raw_token.encode()).hexdigest()),
        )
        connection.execute(
            "INSERT INTO audit_events (user_account_id, event_type, outcome, details) VALUES (%s, 'administrator.bootstrap', 'success', %s)",
            (account["id"], Jsonb({"contact_id": str(args.contact_id)})),
        )

    print(f"{frontend_url}/?invitation={raw_token}")


if __name__ == "__main__":
    main()

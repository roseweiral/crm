"""Demo user accounts and fake-provider identities without durable sessions."""

import os

from demo.context import DemoContext


def populate(context: DemoContext) -> int:
    issuer = os.environ.get("FAKE_OIDC_ISSUER", "http://fake-oidc:9000")
    accounts = [
        {
            "id": context.stable_uuid("user-account", contact["id"]),
            "contact_id": contact["id"],
            "status": "active",
        }
        for contact in context.rows["contacts"]
        if contact["can_login"]
    ]

    identities = [
        {
            "id": context.stable_uuid("user-identity", contact["id"]),
            "user_account_id": context.stable_uuid("user-account", contact["id"]),
            "provider": "google",
            "issuer": issuer,
            "subject": str(contact["id"]),
            "email": contact["email"],
            "email_verified": True,
            "last_signed_in_at": None,
        }
        for contact in context.rows["contacts"]
        if contact["can_login"]
    ]

    context.set_rows("user_identities", identities)
    context.set_rows("invitations", [])
    context.set_rows("user_sessions", [])
    return context.set_rows("user_accounts", accounts)

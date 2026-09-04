"""Demo permissions and an explicit Global System Administrator assignment."""

from demo.context import DemoContext


def populate(context: DemoContext) -> int:
    read_permission_id = context.stable_uuid("permission", "crm.read")
    global_role_id = context.stable_uuid("access-role", "global-system-admin")
    reader_role_id = context.stable_uuid("access-role", "organisational-reader")
    context.set_rows(
        "permissions",
        [{"id": read_permission_id, "name": "crm.read", "description": "Read CRM information within the effective scope"}],
    )
    context.set_rows(
        "access_roles",
        [
            {"id": global_role_id, "name": "Global System Administrator", "description": "Read all CRM information", "is_global": True},
            {"id": reader_role_id, "name": "Organisational Reader", "description": "Read group and descendant information", "is_global": False},
        ],
    )
    context.set_rows(
        "access_role_permissions",
        [
            {"access_role_id": global_role_id, "permission_id": read_permission_id},
            {"access_role_id": reader_role_id, "permission_id": read_permission_id},
        ],
    )
    accounts = context.rows["user_accounts"]
    assignments = []
    if accounts:
        assignments.append(
            {
                "id": context.stable_uuid("user-access-role", "global-admin"),
                "user_account_id": accounts[0]["id"],
                "access_role_id": global_role_id,
                "group_id": None,
                "start_date": context.config.as_of_date,
                "end_date": None,
            }
        )
    context.set_rows("audit_events", [])
    return context.set_rows("user_access_role_assignments", assignments)

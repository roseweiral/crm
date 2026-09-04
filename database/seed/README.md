# Seed data

These CSV files contain deterministic data used to initialise a blank database.

- UUIDs and foreign-key UUIDs are supplied explicitly.
- `created_at` and `modified_at` are omitted so PostgreSQL applies their defaults.
- Empty nullable values should be represented by an empty CSV field.
- IDs should remain stable once other files refer to them.

Load the files in this dependency order:

1. `contacts.csv`
2. `user_accounts.csv`
3. `user_identities.csv`
4. `invitations.csv`
5. `user_sessions.csv`
6. `role_types.csv`
7. `group_types.csv`
8. `family_units.csv`
9. `award_types.csv`
10. `groups.csv`
11. `contact_roles_groups.csv`
12. `contact_family_units.csv`
13. `contact_awards.csv`
14. `permissions.csv`
15. `access_roles.csv`
16. `access_role_permissions.csv`
17. `user_access_role_assignments.csv`
18. `audit_events.csv`

The first contact has an explicit active user account and is reserved as the seeded
Global System Administrator. Its access is represented by an explicit access-role
assignment; code must never infer permissions from CSV row order.

Every seeded contact has a unique fictional email, `can_login=true`, an active user
account, and a Google identity matching the development fake OIDC provider.

All primary and foreign keys are UUIDs. Seed UUIDs should remain stable once other
files refer to them.

From the repository root, import all seed files with:

```shell
docker compose run --rm app python /database/import_seed.py
```

The importer validates every CSV header before inserting its rows. All inserts run
inside one transaction, so an error leaves the database unchanged. Group rows must
place parents before their children within `groups.csv`.

For `APP_ENV=development` or `APP_ENV=test`, the seed files are also imported
automatically immediately after `schema.sql` creates a fresh PostgreSQL database.
PostgreSQL only runs this automatic initialization for a new, empty database volume.

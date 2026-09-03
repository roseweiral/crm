# Seed data

These CSV files contain deterministic data used to initialise a blank database.

- UUIDs and foreign-key UUIDs are supplied explicitly.
- `created_at` and `modified_at` are omitted so PostgreSQL applies their defaults.
- Empty nullable values should be represented by an empty CSV field.
- IDs should remain stable once other files refer to them.

Load the files in this dependency order:

1. `contacts.csv`
2. `role_types.csv`
3. `group_types.csv`
4. `family_units.csv`
5. `award_types.csv`
6. `groups.csv`
7. `contact_roles_groups.csv`
8. `contact_family_units.csv`
9. `contact_awards.csv`

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

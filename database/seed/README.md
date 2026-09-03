# Seed data

These CSV files contain deterministic data used to initialise a blank database.

- IDs and foreign-key IDs are supplied explicitly.
- `created_at` and `modified_at` are omitted so PostgreSQL applies their defaults.
- Empty nullable values should be represented by an empty CSV field.
- IDs should remain stable once other files refer to them.

Load the files in this dependency order:

1. `contacts.csv`
2. `role_types.csv`
3. `group_types.csv`
4. `families.csv`
5. `award_types.csv`
6. `groups.csv`
7. `contact_roles_groups.csv`
8. `contact_families.csv`
9. `contact_awards.csv`

After importing, each table's identity sequence must be advanced beyond its highest supplied ID.

From the repository root, import all seed files with:

```shell
docker compose run --rm app python /database/import_seed.py
```

The importer validates every CSV header before inserting its rows. All inserts run
inside one transaction, so an error leaves the database unchanged. Group rows must
place parents before their children within `groups.csv`.

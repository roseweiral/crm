# Database migrations

Database initialization scripts only run on a fresh volume. Existing installations
must apply migrations in order before deploying the corresponding API changes.
Take a database backup and schedule the index build for a maintenance window: this
small initial migration uses a transactional index build that blocks concurrent writes.

## 001 — contact email uniqueness

Run this read-only check in the target database:

```sql
SELECT lower(btrim(email)) AS normalized_email, count(*)
FROM contacts
WHERE email IS NOT NULL
GROUP BY lower(btrim(email))
HAVING count(*) > 1;
```

Resolve any duplicate ownership explicitly before applying the migration. It does
not merge or delete contacts and does not change stored emails. Nulls remain allowed.
Then run the script with psql's stop-on-error option against the intended database:

```shell
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/migrations/001_contact_email_uniqueness.sql
```

The script is transactional and can be rerun. Fresh databases already contain the
same index in `schema.sql`. Do not reset an existing database to apply migrations.

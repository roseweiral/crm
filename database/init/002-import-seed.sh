#!/bin/sh
set -eu

if [ "${APP_ENV}" = "development" ] || [ "${APP_ENV}" = "test" ]; then
  echo "Importing ${APP_ENV} seed data"

  psql --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" --set ON_ERROR_STOP=1 <<'SQL'
BEGIN;

\copy contacts (id, first_name, last_name, email, status, can_login) FROM '/seed/contacts.csv' WITH (FORMAT csv, HEADER true)
\copy role_types (id, name, description) FROM '/seed/role_types.csv' WITH (FORMAT csv, HEADER true)
\copy group_types (id, name, description) FROM '/seed/group_types.csv' WITH (FORMAT csv, HEADER true)
\copy family_units (id) FROM '/seed/family_units.csv' WITH (FORMAT csv, HEADER true)
\copy award_types (id, name, description) FROM '/seed/award_types.csv' WITH (FORMAT csv, HEADER true)
\copy groups (id, group_type_id, name, description, parent_id) FROM '/seed/groups.csv' WITH (FORMAT csv, HEADER true)
\copy contact_roles_groups (id, contact_id, role_type_id, group_id, start_date, end_date) FROM '/seed/contact_roles_groups.csv' WITH (FORMAT csv, HEADER true)
\copy contact_family_units (id, contact_id, family_unit_id, relationship) FROM '/seed/contact_family_units.csv' WITH (FORMAT csv, HEADER true)
\copy contact_awards (id, contact_id, award_type_id, status, nomination_date, presented_date, notes) FROM '/seed/contact_awards.csv' WITH (FORMAT csv, HEADER true)

COMMIT;
SQL

  echo "${APP_ENV} seed data imported"
else
  echo "Seed import skipped for APP_ENV=${APP_ENV}"
fi

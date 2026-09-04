# Demo data design

## Purpose

The demo-data generator creates a coherent fictional organisation for local
development and automated testing. The same generated records can be written
directly to PostgreSQL or exported as CSV files for review and later curation as
seed data.

All names, email addresses, descriptions, assignments, and awards produced by the
generator are fictional. Every primary and foreign key is a UUID.

## Running the generator

The generator runs inside the FastAPI container so it has the same PostgreSQL
driver and environment configuration as the application.

Write to the local development database:

```shell
docker compose run --rm app python /database/demo_data.py
```

Replace all existing CRM records before writing:

```shell
docker compose run --rm app python /database/demo_data.py --replace
```

Write CSV files instead of touching PostgreSQL:

```shell
docker compose run --rm app python /database/demo_data.py --output csv
```

The default CSV destination is `database/generated`. It is deliberately separate
from `database/seed`, preventing generated output from overwriting curated seed
files.

## Record-count options

The main record counts are configurable:

```shell
docker compose run --rm app python /database/demo_data.py \
  --contacts 120 \
  --families 30 \
  --groups 12 \
  --replace
```

- `--contacts` is the total number of adults and children.
- `--families` creates one anonymous family unit with one parent and one child
  relationship.
- `--groups` is the number of local leaf units, not the total number of rows in
  the `groups` table. The required management hierarchy is added automatically.
- The contact count must be at least twice the family count and must leave enough
  adults for leadership roles.

`--random-seed` controls repeatability. Using the same options, random seed, and
as-of date produces the same records, including every UUID. `--as-of-date` accepts
an ISO date and is used as the reference point for role and award dates.

## Organisation hierarchy

The first version generates this hierarchy:

```text
HQ
└── Greater London (County)
    └── London (City)
        ├── Croydon (Town)
        │   ├── Croydon Group 1
        │   └── Croydon Group 2
        └── Bromley (Town)
            └── Bromley Group 1
```

One town is created for every three requested local groups. Local groups are
distributed across the towns. Additional town names come from Faker after the
preferred starter names have been used.

## Role logic

Generated children never receive organisational roles.

Every local group receives:

- one Group Leader;
- two Group Helpers.

Every management-level record—HQ, County, City, and Town—receives one Area
Manager. Adults are reused when the number of assignments exceeds the number of
available adults. All initial assignments start on 1 January in the as-of date's
year and have no end date.

## Families and contacts

Each anonymous family unit is identified only by a deterministic UUID. It has no
stored name or assumed shared surname. Each unit receives one adult contact with
the `parent` relationship and one child contact with the `child` relationship.
Every generated contact receives a unique fictional email address and has
`can_login=true`, allowing every development identity to exercise authentication.

## Awards

The generator creates three award types and assigns awards to approximately one
quarter of contacts. Each generated contact and award-type pair is unique, in
line with the database constraint. Award states are distributed across nominated,
approved, presented, and declined.

## Output and safety

Database output is accepted only when `APP_ENV` is `development` or `test`.
Production database output is rejected. Without `--replace`, database output also
refuses to run when any CRM table already contains records.

CSV output does not connect to PostgreSQL. Every output file has the same columns
as its corresponding seed CSV, including explicit stable UUIDs but excluding
database-managed timestamps.

The Docker tester runs the generator with `--replace` before executing the test
suite, making test runs repeatable against the disposable local database.

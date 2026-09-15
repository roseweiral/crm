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
Each family's parent is also set as that family's current Main Contact
(`contact_family_main_contacts`), so the write-access model in
`documents/contact-data-expansion-design.md` has real data to exercise from
the first run - no dev/test environment goes through demo data with an
un-set Main Contact.

## Contact details (contact-data-expansion-design.md)

Every field and table added for [`contact-data-expansion-design.md`](contact-data-expansion-design.md)
is populated, deliberately with realistic sparsity - not every contact has
every field, matching how a real volunteer CRM's data actually looks after
a schema expansion (existing records don't retroactively gain complete data).

- **Personal details** (`date_of_birth`, `preferred_name`, `phonetic_name`,
  `pronouns`, `gender`, directly on `contacts`): roughly 70% of contacts get
  a plausible date of birth (adults 22-72, children 5-17); 15% get a
  preferred name; 50% get a gender/pronouns pair, consistent with each
  other. `phonetic_name` only appears for the small, curated set of real
  first names in `database/demo/contacts.py`'s `PHONETIC_RESPELLINGS` (for
  example Siobhan, Niamh, Euan) - most contacts have none, which is
  realistic; nothing is invented for names that don't need a phonetic
  spelling.
- **Phone numbers and addresses** (adults only): about 85% of adults get one
  primary mobile number, a quarter of those also get a second, non-primary
  number; about 75% of adults get one current home address. Children don't
  get independent phone numbers or addresses in this dataset.
- **Emergency contacts**: every family's child lists their family's parent
  as a real `family_relationship`-backed emergency contact
  (`relationship = "Parent"`). About 80% of adults - family parents
  included - also get a plausible non-family emergency contact (a
  different random adult, `relationship` one of Partner/Sibling/Friend/
  Neighbour), matching the design's "not every emergency contact is an
  existing family relationship" intent. Each contact has at most one
  emergency-contact entry in this dataset.

### Backfilling the curated seed CSVs

`database/seed/*.csv` predate these fields - they're hand-curated (see
`database/seed/README.md`; at least one row's name has been manually
changed from its generated value) rather than a live `demo_data.py
--output csv` snapshot, so they can't simply be regenerated without losing
that curation. `database/backfill_seed_expansion.py` is a one-off script
that adds the new columns and tables to the *existing* curated CSVs,
reusing the same generator modules against a context built from the real,
existing IDs rather than freshly generated ones - every previously-curated
row, column, and ID is left untouched. See that script's docstring for how
to run it; it's only needed again if the seed CSVs gain more curation this
same way in the future.

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

# Demo data generators

Each module in this package generates records for one database table. The
`database/demo_data.py` runner calls them in dependency order and sends the shared
result to either PostgreSQL or CSV output.

See `documents/demo-data.md` for the generation rules and commands.

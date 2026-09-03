# Demo data generators

Each module in this package is responsible for populating one database table.
The `database/demo_data.py` runner calls them in dependency order.

The modules are intentionally unconfigured. They currently make no database
connection and add no records. Faker and database-writing behavior will be
introduced table by table.

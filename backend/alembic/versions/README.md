# Database migrations

`0001_baseline` is the unchanged phase-one anchor with no business tables.
`0002_core_schema` freezes the fourteen tables from plan 2.1, section 3.9.

From `backend/`, run `python -m alembic upgrade head` after configuring the
database connection. Both a fresh database and an existing `0001_baseline`
database are supported. Run `python -m alembic check` to compare the migrated
schema with ORM metadata. New schema changes require a new revision; do not
edit an already applied migration or call `metadata.create_all()` at startup.

For a disposable test database only, `python -m alembic downgrade 0001_baseline`
removes all fourteen tables and their data. Reapply with `upgrade head`.
See `docs/stage2-contracts.md` at the repository root for the contract map and
opt-in PostgreSQL integration tests.

# Migrations

The API and local ingestion CLI apply migrations automatically on startup. Set
`CREATE_DB_ON_STARTUP=false` when the deployment runs migrations separately.

From the backend directory, run `alembic upgrade head` to migrate a managed
database using `DATABASE_URL`. Revision 0001 creates the evidence tables; 0002
adds source provenance and the ingestion run journal.

The automatic initializer also recognizes the complete original unmanaged
SQLite scaffold schema, stamps it as revision 0001, and upgrades it while
preserving its records. Existing demo records are not reseeded or overwritten;
a fresh database receives the current demo scenarios when `SEED_DEMO_DATA=true`.
Back up existing databases before upgrading a deployed installation.

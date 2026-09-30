from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect
from sqlalchemy.orm import Session

from app.db.seed import seed_demo_data
from app.db.session import engine


def init_db(*, seed_demo: bool = True, bind: Engine | None = None) -> None:
    """Migrate fresh databases and recognize the original unmanaged scaffold schema."""
    bind = bind or engine
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    with bind.begin() as connection:
        config.attributes["connection"] = connection
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        if "alembic_version" not in tables and "threat_events" in tables:
            baseline = {"source_items", "threat_events", "threat_sources", "threat_scores", "extracted_claims", "threat_timeline_entries"}
            if not baseline.issubset(tables):
                raise RuntimeError("Database schema is incomplete; cannot recognize the initial release")
            has_provenance = any(column["name"] == "provenance" for column in inspector.get_columns("source_items"))
            has_map_location = any(column["name"] == "map_location" for column in inspector.get_columns("threat_events"))
            revision = "0001_initial_threat_tables"
            if has_provenance and "ingestion_runs" in tables:
                revision = "0003_map_locations" if has_map_location else "0002_ingestion_provenance"
            command.stamp(config, revision)
        command.upgrade(config, "head")
    if seed_demo:
        with Session(bind) as session:
            seed_demo_data(session)

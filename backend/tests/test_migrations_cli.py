from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.cli import main
from app.db.init import init_db
from app.db.repository import list_threat_events


def test_migration_recognizes_old_scaffold_and_preserves_data(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "app/db/migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001_initial_threat_tables")
        connection.execute(text("INSERT INTO source_items (id,title,source_name,source_type,reliability_tier,citation,is_official,is_demo) VALUES ('legacy','Old source','Agency','official','very_high','Legacy citation',1,1)"))
        connection.execute(text("DROP TABLE alembic_version"))
    init_db(seed_demo=False, bind=engine)
    with engine.connect() as connection:
        row = connection.execute(text("SELECT title, provenance FROM source_items WHERE id='legacy'")).one()
        assert row.title == "Old source" and row.provenance == "{}"
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0003_map_locations"
    assert "ingestion_runs" in inspect(engine).get_table_names()
    init_db(seed_demo=False, bind=engine)
    engine.dispose()


def test_cli_fixture_migrates_fresh_database_and_repeats_without_duplicates(tmp_path, capsys):
    database_url = f"sqlite:///{tmp_path / 'cli.db'}"
    args = ["ingest", "--connector", "usgs_earthquakes", "--fixture", str(Path(__file__).parent / "fixtures/usgs_earthquakes.json"), "--database-url", database_url]
    assert main(args) == 0
    assert '"inserted": 1' in capsys.readouterr().out
    assert main(args) == 0
    assert '"unchanged": 1' in capsys.readouterr().out
    engine = create_engine(database_url)
    with Session(engine) as session:
        threat, = list_threat_events(session)
        assert threat.is_demo is True and len(threat.timeline) == 1
    engine.dispose()


def test_cli_fixture_all_is_rejected():
    with pytest.raises(SystemExit) as error:
        main(["ingest", "--connector", "all", "--fixture", "ignored.json"])
    assert error.value.code == 2


def test_map_migration_preserves_existing_events_without_guessing_coordinates(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'before-map.db'}")
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "app/db/migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0002_ingestion_provenance")
        connection.execute(text("""INSERT INTO threat_events
            (id,title,category,geography,status,summary,key_uncertainties,contradictory_evidence,
             next_watch_items,implications,updated_at,is_demo)
            VALUES ('existing','Existing evidence','natural_hazard','["Unknown location"]','confirmed',
                    'No point supplied','[]','[]','[]','[]','2026-04-26 12:00:00',0)"""))
    init_db(seed_demo=False, bind=engine)
    init_db(seed_demo=False, bind=engine)
    with engine.connect() as connection:
        row = connection.execute(text("SELECT title, geography, map_location FROM threat_events WHERE id='existing'")).one()
        assert row.title == "Existing evidence"
        assert row.geography == '["Unknown location"]'
        assert row.map_location is None
    engine.dispose()

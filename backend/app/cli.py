"""Local-only ingestion commands; the HTTP API exposes no mutation endpoints."""

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.connectors.http import MAX_FEED_BYTES
from app.core.config import get_settings
from app.db.init import init_db
from app.db.session import make_engine
from app.domain.ingestion.registry import registry
from app.domain.ingestion.service import ingest_connector


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    ingest = subcommands.add_parser("ingest", help="Fetch official feeds or load visibly labeled demo fixtures")
    ingest.add_argument("--connector", required=True, choices=[*registry.names(), "all"])
    ingest.add_argument("--fixture", type=Path, help="Local JSON fixture; always stored as demo data")
    ingest.add_argument("--database-url", help="Override DATABASE_URL for this command")
    news = subcommands.add_parser("news", help="Bounded NASA news snapshots, separate from the SQL threat store")
    news_commands = news.add_subparsers(dest="news_command", required=True)
    news_ingest = news_commands.add_parser("ingest", help="Fetch or revalidate the official NASA RSS snapshot")
    news_ingest.add_argument("--cache-path", type=Path, help="Override NEWS_SNAPSHOT_PATH for this command")
    args = parser.parse_args(argv)
    if args.command == "news":
        from app.news.service import ingest_news
        result = asyncio.run(ingest_news(args.cache_path or Path(get_settings().news_snapshot_path)))
        print(json.dumps({"edition": result.edition, "fetch_state": result.fetch_state,
                          "events": len(result.events), "articles": sum(len(event.articles) for event in result.events),
                          "fetched_at": result.fetched_at.isoformat() if result.fetched_at else None,
                          "last_attempt_at": result.last_attempt_at.isoformat() if result.last_attempt_at else None,
                          "duplicates_excluded": result.duplicates_excluded, "error": result.error}))
        return 1 if result.fetch_state == "error" else 0
    if args.fixture is not None and args.connector == "all":
        parser.error("--fixture requires a single --connector")
    fixture = None
    if args.fixture is not None:
        try:
            if args.fixture.stat().st_size > MAX_FEED_BYTES:
                parser.error("fixture exceeds 10 MiB")
            fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
            if not isinstance(fixture, dict):
                parser.error("fixture must contain a JSON object")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            parser.error("could not read fixture as JSON")
    database_url = args.database_url or get_settings().database_url
    engine = make_engine(database_url)
    init_db(seed_demo=False, bind=engine)

    async def run_ingestion() -> int:
        failures = 0
        with Session(engine, expire_on_commit=False) as session:
            for name in registry.names() if args.connector == "all" else [args.connector]:
                run = await ingest_connector(session, registry.get(name), fixture=fixture)
                print(json.dumps({"connector": name, "data_mode": run.data_mode, "success": run.success,
                                  "items": run.item_count, "inserted": run.inserted_count,
                                  "updated": run.updated_count, "unchanged": run.unchanged_count,
                                  "error": run.error}))
                failures += int(not run.success)
        return 1 if failures else 0

    try:
        return asyncio.run(run_ingestion())
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())

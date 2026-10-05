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


def _print_news_result(result) -> None:
    records = [article for event in result.events for article in event.articles]
    print(json.dumps({"edition": result.edition, "fetch_state": result.fetch_state,
                      "events": len(result.events), "articles": sum(article.record_kind == "article" for article in records),
                      "official_reports": sum(article.record_kind == "official_report" for article in records),
                      "fetched_at": result.fetched_at.isoformat() if result.fetched_at else None,
                      "last_attempt_at": result.last_attempt_at.isoformat() if result.last_attempt_at else None,
                      "duplicates_excluded": result.duplicates_excluded, "error": result.error,
                      "sources": [source.model_dump(mode="json") for source in result.sources]}), flush=True)


def _review(parser: argparse.ArgumentParser, args) -> int:
    from pydantic import ValidationError
    from app.core.time import utc_now
    from app.news.review import ReviewError, describe, load_reviews, save_reviews
    from app.news.service import read_sources
    from app.news.models import PlacementReview
    from app.news.urls import canonical_url
    path = args.cache_path or Path(get_settings().news_snapshot_path)
    try:
        reviews = load_reviews(path)
        if args.list:
            print(json.dumps([describe(review) for review in reviews.values()]))
            return 0
        try:
            url = canonical_url(args.url)
        except ValueError:
            parser.error("--url must be a safe http(s) article URL")
        if args.clear:
            if reviews.pop(url, None) is None:
                parser.error("no review is stored for this URL")
            save_reviews(path, reviews)
            print(json.dumps({"cleared": url}))
            return 0
        if not (args.confirm or args.move or args.remove):
            parser.error("choose --confirm, --move LAT LON, --remove or --clear")
        if not args.note or not args.reviewer:
            parser.error("--note and --reviewer are required")
        if bool(args.move) != bool(args.label):
            parser.error("--label is required with --move and only with --move")
        news = read_sources(path, channel="all")
        event = next((event for event in news.events for article in event.articles
                      if url in (article.canonical_url, *article.duplicate_urls)), None)
        if event is None:
            parser.error("no stored article has this URL")
        if args.confirm and (event.location is None or event.placement_review is not None and event.placement_review.action == "moved"):
            parser.error("only an automatic map position can be confirmed")
        review = PlacementReview(
            article_url=url, action="confirmed" if args.confirm else "moved" if args.move else "removed",
            note=args.note, reviewer=args.reviewer, reviewed_at=utc_now(),
            reviewed_label=event.location.label if args.confirm else None,
            lat=args.move[0] if args.move else None, lon=args.move[1] if args.move else None, place_label=args.label)
        reviews[url] = review
        save_reviews(path, reviews)
        print(json.dumps({"event": event.id, "title": event.title, "review": describe(review)}))
        return 0
    except ValidationError as error:
        print(json.dumps({"error": "; ".join(item["msg"] for item in error.errors())[:300]}))
        return 1
    except ReviewError as error:
        print(json.dumps({"error": str(error)}))
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    ingest = subcommands.add_parser("ingest", help="Fetch official feeds or load visibly labeled demo fixtures")
    ingest.add_argument("--connector", required=True, choices=[*registry.names(), "all"])
    ingest.add_argument("--fixture", type=Path, help="Local JSON fixture; always stored as demo data")
    ingest.add_argument("--database-url", help="Override DATABASE_URL for this command")
    news = subcommands.add_parser("news", help="Bounded public RSS snapshots, separate from the SQL threat store")
    news_commands = news.add_subparsers(dest="news_command", required=True)
    news_ingest = news_commands.add_parser("ingest", help="Fetch or revalidate independent public RSS snapshots")
    news_ingest.add_argument("--cache-path", type=Path, help="NASA cache path; other feeds use deterministic sibling files")
    news_ingest.add_argument("--source", choices=["all", "globalvoices", "gdelt", "wikipedia", "gdacs", "nasa"], default="all")
    news_poll = news_commands.add_parser("poll", help="Explicitly run one GDELT polling queue; never starts with the HTTP app")
    news_poll.add_argument("--source", choices=["gdelt"], default="gdelt")
    news_poll.add_argument("--cache-path", type=Path)
    news_poll.add_argument("--interval-seconds", type=int, help="900–86400; defaults to NEWS_POLL_INTERVAL_SECONDS")
    news_review = news_commands.add_parser(
        "review", help="Confirm, move or remove the map position of the event containing an article (local operator action)")
    news_review.add_argument("--cache-path", type=Path)
    review_target = news_review.add_mutually_exclusive_group(required=True)
    review_target.add_argument("--url", help="Article URL as stored in the news snapshot")
    review_target.add_argument("--list", action="store_true", help="Print stored reviews")
    review_action = news_review.add_mutually_exclusive_group()
    review_action.add_argument("--confirm", action="store_true", help="The automatic position matches the sources")
    review_action.add_argument("--move", nargs=2, type=float, metavar=("LAT", "LON"), help="Set the position the sources support")
    review_action.add_argument("--remove", action="store_true", help="The sources support no single map position")
    review_action.add_argument("--clear", action="store_true", help="Delete the review for this article")
    news_review.add_argument("--label", help="Place name for --move, such as 'Jabalia, Gaza Strip'")
    news_review.add_argument("--note", help="Why: which source supports the decision")
    news_review.add_argument("--reviewer", help="Who reviewed it")
    args = parser.parse_args(argv)
    if args.command == "news" and args.news_command == "review":
        return _review(parser, args)
    if args.command == "news":
        from app.news.service import ingest_sources
        from app.news.polling import NewsLockError, news_lock, poll_news
        path = args.cache_path or Path(get_settings().news_snapshot_path)
        interval = getattr(args, "interval_seconds", None)
        if args.news_command == "poll":
            interval = interval if interval is not None else get_settings().news_poll_interval_seconds
            if not 900 <= interval <= 86400:
                parser.error("--interval-seconds must be between 900 and 86400")
        try:
            with news_lock(path):
                if args.news_command == "poll":
                    asyncio.run(poll_news(path, interval_seconds=interval, on_result=_print_news_result))
                    return 0
                result = asyncio.run(ingest_sources(path, source=args.source))
        except NewsLockError as error:
            print(json.dumps({"error": str(error)}))
            return 1
        except KeyboardInterrupt:
            return 130
        _print_news_result(result)
        selected = result.sources if args.source == "all" else [source for source in result.sources if source.source_id == args.source]
        return 1 if any(source.state == "error" for source in selected) else 0
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

"""Explicit, single-process CLI polling. Importing this module starts no worker."""

import asyncio
from contextlib import contextmanager
from datetime import datetime
import os
from pathlib import Path
import uuid

from app.core.time import utc_now
from app.news.models import NewsResponse
from app.news.service import ingest_sources


class NewsLockError(RuntimeError):
    pass


@contextmanager
def news_lock(path: Path | str):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = target.with_name(target.name + ".lock")
    token = f"{os.getpid()} {uuid.uuid4().hex}\n".encode("ascii")
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise NewsLockError("Another news import or poller holds this cache lock. A leftover lock requires operator verification before removal.") from error
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(token)
            stream.flush()
        yield
    finally:
        try:
            if lock.read_bytes() == token:
                lock.unlink()
        except FileNotFoundError:
            pass


def poll_delay(response: NewsResponse, interval_seconds: int, now: datetime) -> float:
    next_fetch = next((source.next_fetch_at for source in response.sources if source.source_id == "gdelt"), None)
    return max(float(interval_seconds), (next_fetch - now).total_seconds() if next_fetch else 0.0)


async def poll_news(path: Path | str, *, interval_seconds: int, stop_event: asyncio.Event | None = None,
                    on_result=None) -> None:
    if not 900 <= interval_seconds <= 86400:
        raise ValueError("Polling interval must be between 900 and 86400 seconds")
    stop = stop_event or asyncio.Event()
    while not stop.is_set():
        # Await each import before scheduling another; only GDELT is polled.
        result = await ingest_sources(path, source="gdelt")
        if on_result:
            on_result(result)
        delay = poll_delay(result, interval_seconds, utc_now())
        try:
            await asyncio.wait_for(stop.wait(), timeout=delay)
        except TimeoutError:
            continue

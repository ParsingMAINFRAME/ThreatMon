"""Explicit, single-process CLI polling. Importing this module starts no worker."""

import asyncio
from contextlib import contextmanager
from datetime import datetime
import os
from pathlib import Path
import socket
import uuid

from app.core.time import utc_now
from app.news.models import NewsResponse
from app.news.service import ingest_sources


# A one-shot import finishes well inside this; a poller renews its claim past each wait.
LOCK_SECONDS = 600
# Lock identities held by this process, so a nested claim is never mistaken for a dead earlier owner.
_HELD_IDENTITIES: set[str] = set()


class NewsLockError(RuntimeError):
    pass


@contextmanager
def news_lock(path: Path | str):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = target.with_name(target.name + ".lock")
    identity = f"{os.getpid()} {uuid.uuid4().hex}"

    host = socket.gethostname().replace(" ", "_") or "unknown"

    def token(seconds: float) -> bytes:
        return f"{identity} {int(utc_now().timestamp() + seconds)} {host}\n".encode("ascii")

    def create() -> int:
        return os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        descriptor = create()
    except FileExistsError as error:
        # An owner that was killed cannot release its lock. Each owner writes when its claim expires and a
        # poller renews it every cycle, so a lock past its own expiry is reclaimed. A lock written on this host
        # under this process's own PID by an identity this process does not hold is also dead: a restarted
        # container runs its poller as PID 1 again, and no other live process can share that PID.
        try:
            fields = lock.read_bytes().decode("ascii").split()
            expired = int(fields[2]) < utc_now().timestamp()
            dead_earlier_self = (len(fields) >= 4 and fields[0] == str(os.getpid()) and fields[3] == host
                                 and f"{fields[0]} {fields[1]}" not in _HELD_IDENTITIES)
        except (OSError, IndexError, ValueError, UnicodeDecodeError):
            expired = dead_earlier_self = False  # Unreadable or older-format locks still require operator verification.
        if not (expired or dead_earlier_self):
            raise NewsLockError("Another news import or poller holds this cache lock. A leftover lock requires operator verification before removal.") from error
        lock.unlink(missing_ok=True)
        try:
            descriptor = create()
        except FileExistsError as race:
            raise NewsLockError("Another news import or poller holds this cache lock.") from race

    def renew(seconds: float) -> None:
        if lock.read_bytes().startswith(identity.encode("ascii")):
            lock.write_bytes(token(seconds))
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(token(LOCK_SECONDS))
            stream.flush()
        _HELD_IDENTITIES.add(identity)
        yield renew
    finally:
        _HELD_IDENTITIES.discard(identity)
        try:
            if lock.read_bytes().startswith(identity.encode("ascii")):
                lock.unlink()
        except FileNotFoundError:
            pass


POLLED_SOURCES = ("gdelt", "wikipedia", "globalvoices")


def poll_delay(response: NewsResponse, interval_seconds: int, now: datetime, sources: tuple[str, ...] = ("gdelt",)) -> float:
    """Wait at least the interval, and until the soonest polled source permits another request."""
    waits = [(source.next_fetch_at - now).total_seconds() for source in response.sources
             if source.source_id in sources and source.next_fetch_at]
    return max(float(interval_seconds), min(waits) if waits else 0.0)


async def poll_news(path: Path | str, *, interval_seconds: int, stop_event: asyncio.Event | None = None,
                    on_result=None, sources: tuple[str, ...] = ("gdelt",), renew_lock=None) -> None:
    if not sources or any(source not in POLLED_SOURCES for source in sources):
        raise ValueError("Only news sources can be polled")
    if not 900 <= interval_seconds <= 86400:
        raise ValueError("Polling interval must be between 900 and 86400 seconds")
    stop = stop_event or asyncio.Event()
    while not stop.is_set():
        # One queue: await each source in turn before scheduling the next cycle. Every source keeps its own
        # cooldown and failure backoff, so a source that is not yet due makes no request.
        for source in sources:
            result = await ingest_sources(path, source=source)
            if on_result:
                on_result(result)
            if stop.is_set():
                return
        delay = poll_delay(result, interval_seconds, utc_now(), sources)
        if renew_lock:
            renew_lock(delay + LOCK_SECONDS)
        try:
            await asyncio.wait_for(stop.wait(), timeout=delay)
        except TimeoutError:
            continue

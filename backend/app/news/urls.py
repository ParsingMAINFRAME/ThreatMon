"""Conservative URL and declared-syndication deduplication; never semantic clustering."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

if TYPE_CHECKING:
    from app.news.models import NewsArticle

TRACKING_KEYS = {"fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid", "_ga", "_gl"}


def canonical_url(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 4096 or any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("Invalid news URL")
    try:
        parsed = urlsplit(value)
        scheme = parsed.scheme.lower()
        host = (parsed.hostname or "").encode("idna").decode("ascii").lower()
        if scheme not in {"http", "https"} or parsed.username is not None or parsed.password is not None:
            raise ValueError
        if not host or "." not in host or host.endswith((".local", ".localhost", ".internal")) or "\\" in host:
            raise ValueError
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError
        if parsed.port is not None and parsed.port != (443 if scheme == "https" else 80):
            raise ValueError
        query = [(key, val) for key, val in parse_qsl(parsed.query, keep_blank_values=True, max_num_fields=100)
                 if not key.lower().startswith("utm_") and key.lower() not in TRACKING_KEYS]
        # Sort keys, retaining the order of repeated values (which may be semantic).
        query.sort(key=lambda pair: pair[0])
        return urlunsplit((scheme, host, parsed.path or "/", urlencode(query), ""))
    except (ValueError, UnicodeError) as error:
        raise ValueError("Invalid news URL") from error


@dataclass(frozen=True)
class ArticleCandidate:
    article: NewsArticle
    # Demo-only internal identity; never exposed as a fake clickable source URL.
    identity_url: str | None = None


def deduplicate_articles(candidates: list[ArticleCandidate]) -> tuple[list[NewsArticle], int]:
    parents = list(range(len(candidates)))
    identities: dict[tuple[str, str], int] = {}

    def root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    urls = [canonical_url(item.identity_url or item.article.canonical_url) if item.identity_url or item.article.canonical_url else None for item in candidates]
    for index, candidate in enumerate(candidates):
        keys = ([('url', urls[index])] if urls[index] else [])
        if candidate.article.syndication_key:
            keys.append(('syndication', candidate.article.syndication_key))
        for key in keys:
            if key in identities:
                parents[root(index)] = root(identities[key])
            else:
                identities[key] = index
    groups: dict[int, list[int]] = {}
    for index in range(len(candidates)):
        groups.setdefault(root(index), []).append(index)
    retained = []
    for members in groups.values():
        representative = min(members, key=lambda index: (urls[index] or "", candidates[index].article.publisher.casefold(), candidates[index].article.id))
        item = candidates[representative].article.model_copy(deep=True)
        if not item.is_demo:
            duplicate_urls = {url for index in members for url in candidates[index].article.duplicate_urls}
            duplicate_urls.update(urls[index] for index in members if urls[index] and urls[index] != item.canonical_url)
            item.duplicate_urls = sorted(duplicate_urls)
        retained.append(item)
    retained.sort(key=lambda item: item.id)
    return retained, len(candidates) - len(retained)

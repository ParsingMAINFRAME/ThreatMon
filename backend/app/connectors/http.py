"""Bounded read-only JSON fetching for fixed public agency feeds."""

import asyncio
import json

import httpx


MAX_FEED_BYTES = 10 * 1024 * 1024


class FeedError(ValueError):
    """A feed could not be fetched or its schema could not be validated."""


async def fetch_json(url: str, client: httpx.AsyncClient | None = None) -> dict:
    if client is None:
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=False,
            headers={"User-Agent": "ThreatSituationRoom/0.2 (read-only public-feed client)"},
        ) as owned_client:
            return await fetch_json(url, owned_client)

    for attempt in range(3):
        try:
            async with client.stream("GET", url, timeout=15) as response:
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_FEED_BYTES:
                        raise FeedError("Feed exceeds the 10 MiB size limit")
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise FeedError("Feed must contain a JSON object")
            return payload
        except (httpx.TransportError, httpx.HTTPStatusError) as error:
            retryable = isinstance(error, httpx.TransportError) or error.response.status_code >= 500 or error.response.status_code == 429
            if retryable and attempt < 2:
                await asyncio.sleep(0.25 * (2 ** attempt))
                continue
            raise FeedError(f"Official feed request failed ({type(error).__name__})") from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise FeedError("Feed did not return valid JSON") from error
    raise FeedError("Official feed request failed")

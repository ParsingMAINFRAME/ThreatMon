from app.domain.ingestion.base import Connector, RawSignal


class RssConnector(Connector):
    name = "rss"

    async def fetch(self) -> list[RawSignal]:
        return []

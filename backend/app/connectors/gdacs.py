from app.domain.ingestion.base import Connector, RawSignal


class GdacsConnector(Connector):
    name = "gdacs"

    async def fetch(self) -> list[RawSignal]:
        return []

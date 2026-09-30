from app.domain.ingestion.base import Connector, RawSignal


class NasaNeoConnector(Connector):
    name = "nasa_neo"

    async def fetch(self) -> list[RawSignal]:
        return []

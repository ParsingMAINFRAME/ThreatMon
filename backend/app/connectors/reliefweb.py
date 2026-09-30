from app.domain.ingestion.base import Connector, RawSignal


class ReliefWebConnector(Connector):
    name = "reliefweb"

    async def fetch(self) -> list[RawSignal]:
        return []

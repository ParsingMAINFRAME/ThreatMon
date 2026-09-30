from app.connectors.cisa_kev import CisaKevConnector
from app.connectors.usgs_earthquakes import UsgsEarthquakesConnector
from app.domain.ingestion.base import Connector


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[str, Connector] = {}

    def register(self, connector: Connector) -> None:
        self._connectors[connector.name] = connector

    def names(self) -> list[str]:
        return sorted(self._connectors)

    def get(self, name: str) -> Connector:
        return self._connectors[name]


registry = ConnectorRegistry()

registry.register(CisaKevConnector())
registry.register(UsgsEarthquakesConnector())

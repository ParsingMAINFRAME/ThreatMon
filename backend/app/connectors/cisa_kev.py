from datetime import UTC, datetime
import re

import httpx

from app.connectors.http import FeedError, fetch_json
from app.connectors.validation import ensure_unique, finish_signal, require_text
from app.core.time import utc_now
from app.domain.ingestion.base import Connector, RawSignal
from app.domain.sources.models import SourceType
from app.domain.threats.models import ThreatCategory


def catalog_date(value: object, name: str) -> datetime:
    text = require_text(value, name, max_length=10)
    try:
        return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError as error:
        raise FeedError(f"Invalid {name}") from error


class CisaKevConnector(Connector):
    name = "cisa_kev"
    # CISA maintains this mirror for programmatic use, including when cisa.gov blocks requests.
    feed_url = "https://raw.githubusercontent.com/cisagov/kev-data/develop/known_exploited_vulnerabilities.json"
    catalog_url = "https://www.cisa.gov/known-exploited-vulnerabilities-catalog"
    description = "CISA-maintained KEV JSON mirror; listing confirms known exploitation, not compromise of your assets."

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client

    async def fetch(self) -> list[RawSignal]:
        payload = await fetch_json(self.feed_url, self.client)
        return self.parse(payload, retrieved_at=utc_now())

    def parse(self, payload: dict, *, retrieved_at: datetime, is_demo: bool = False) -> list[RawSignal]:
        if not isinstance(payload.get("vulnerabilities"), list):
            raise FeedError("CISA feed must contain a vulnerabilities array")
        version = require_text(payload.get("catalogVersion"), "CISA catalog version", max_length=100)
        signals = []
        for item in payload["vulnerabilities"]:
            if not isinstance(item, dict):
                raise FeedError("Invalid CISA catalog entry")
            cve = require_text(item.get("cveID"), "CVE ID", max_length=40)
            if not re.fullmatch(r"CVE-\d{4}-\d{4,}", cve):
                raise FeedError("Invalid CVE ID")
            vendor = require_text(item.get("vendorProject"), "CISA vendor", max_length=200)
            product = require_text(item.get("product"), "CISA product", max_length=200)
            name = require_text(item.get("vulnerabilityName"), "CISA vulnerability name")
            added = catalog_date(item.get("dateAdded"), "CISA date added")
            due = catalog_date(item.get("dueDate"), "CISA due date")
            title = f"{cve} — {name}"[:500]
            signals.append(finish_signal(RawSignal(
                id=cve, connector=self.name, external_id=cve,
                title=f"[DEMO] {title}"[:500] if is_demo else title,
                source_name="DEMO CISA-shaped fixture" if is_demo else "CISA Known Exploited Vulnerabilities Catalog",
                source_type=SourceType.OFFICIAL, category=ThreatCategory.CYBERSECURITY,
                citation=f"{'DEMO fixture; ' if is_demo else ''}CISA KEV {cve}; catalog version {version}; {self.catalog_url}",
                url=self.catalog_url, published_at=added, retrieved_at=retrieved_at,
                geography=["Geography not specified by the catalog"],
                claims=[f"CISA lists {cve} in its Known Exploited Vulnerabilities catalog.", f"CISA identifies the affected product as {vendor} {product}.", f"The catalog records a remediation due date of {due.date().isoformat()}; applicability depends on CISA directive scope."],
                details={"vendor": vendor, "product": product, "due_date": due.date().isoformat()},
                provenance={"feed_url": self.feed_url, "catalog_version": version, "catalog_url": self.catalog_url},
                is_official=True, is_demo=is_demo,
            )))
        return ensure_unique(signals)

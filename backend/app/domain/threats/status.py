from enum import StrEnum


class ThreatStatus(StrEnum):
    ROUTINE = "routine"
    WATCHLIST = "watchlist"
    DEVELOPING = "developing"
    CONFIRMED = "confirmed"
    RESOLVED = "resolved"
    CONTRADICTED = "contradicted"
    FALSE = "false"


TERMINAL_STATUSES = {
    ThreatStatus.RESOLVED,
    ThreatStatus.CONTRADICTED,
    ThreatStatus.FALSE,
}


def is_terminal_status(status: ThreatStatus) -> bool:
    return status in TERMINAL_STATUSES


def status_allows_active_monitoring(status: ThreatStatus) -> bool:
    return not is_terminal_status(status)


def normalize_status(value: str) -> ThreatStatus:
    normalized = value.strip().lower().replace(" ", "_")
    return ThreatStatus(normalized)

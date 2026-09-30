import pytest

from app.domain.threats.status import (
    ThreatStatus,
    is_terminal_status,
    normalize_status,
    status_allows_active_monitoring,
)


def test_normalize_status_accepts_case_and_spaces() -> None:
    assert normalize_status("Watchlist") == ThreatStatus.WATCHLIST
    assert normalize_status("false") == ThreatStatus.FALSE


def test_terminal_statuses_do_not_allow_active_monitoring() -> None:
    assert is_terminal_status(ThreatStatus.RESOLVED)
    assert is_terminal_status(ThreatStatus.CONTRADICTED)
    assert is_terminal_status(ThreatStatus.FALSE)
    assert not status_allows_active_monitoring(ThreatStatus.FALSE)


def test_developing_status_allows_active_monitoring() -> None:
    assert status_allows_active_monitoring(ThreatStatus.DEVELOPING)


def test_invalid_status_raises_value_error() -> None:
    with pytest.raises(ValueError):
        normalize_status("breaking")

import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.models import Base


@pytest.fixture(autouse=True)
def prevent_real_network(monkeypatch):
    def block(*args, **kwargs):
        raise AssertionError("Tests must inject a mock transport; real network access is forbidden")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", block)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", block)


@pytest.fixture(autouse=True)
def gdelt_doc_mode(monkeypatch):
    """Existing GDELT tests describe the DOC search contract; bulk-file tests opt in explicitly."""
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "news_gdelt_mode", "doc")


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    with Session(db_engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def feed_fixture():
    def load(name):
        return json.loads((Path(__file__).parent / "fixtures" / f"{name}.json").read_text())
    return load

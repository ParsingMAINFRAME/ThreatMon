from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.data.demo import seeded_threats
from app.db.models import Base
from app.db.repository import get_threat_event, list_source_items, list_threat_events, replace_threats


def test_repository_round_trips_seeded_threats() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        replace_threats(session, seeded_threats())
        session.commit()

        threats = list_threat_events(session)
        sources = list_source_items(session)
        cyber = get_threat_event(session, "demo-exploited-cyber-vulnerability")

    assert len(threats) == 4
    assert len(sources) == 5
    assert cyber is not None
    assert cyber.sources[0].citation.startswith("DEMO-CISA-KEV")
    assert cyber.timeline[0].source_ids == ["demo-source-cyber-001"]

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.demo import seeded_threats
from app.db.models import ThreatEventRecord
from app.db.repository import replace_threats


def seed_demo_data(session: Session) -> bool:
    """Seed local demo threats when the database is empty.

    Returns True when records were inserted.
    """
    existing_id = session.scalar(select(ThreatEventRecord.id).limit(1))
    if existing_id is not None:
        return False

    replace_threats(session, seeded_threats())
    session.commit()
    return True

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import IngestionRunRecord
from app.db.repository import _utc
from app.db.session import get_db
from app.domain.ingestion.registry import registry


router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.get("/connectors")
def list_connectors(db: Session = Depends(get_db)) -> dict[str, object]:
    connectors = []
    for name in registry.names():
        connector = registry.get(name)
        latest = db.scalar(select(IngestionRunRecord).where(IngestionRunRecord.connector == name,
                           IngestionRunRecord.data_mode == "live").order_by(IngestionRunRecord.sequence.desc(), IngestionRunRecord.started_at.desc()).limit(1))
        successful = db.scalar(select(IngestionRunRecord).where(IngestionRunRecord.connector == name,
                              IngestionRunRecord.data_mode == "live", IngestionRunRecord.success.is_(True))
                              .order_by(IngestionRunRecord.sequence.desc(), IngestionRunRecord.finished_at.desc()).limit(1))
        connectors.append({
            "name": name, "feed_url": connector.feed_url, "description": connector.description,
            "state": "never_run" if latest is None else "ok" if latest.success else "error",
            "last_attempt_at": _utc(latest.started_at) if latest else None,
            "last_success_at": _utc(successful.finished_at) if successful else None,
            "item_count": successful.item_count if successful else 0,
            "error": latest.error if latest else None,
        })
    return {
        "live_ingestion_enabled": True,
        "automatic_refresh_enabled": False,
        "connectors": connectors,
        "note": "Read-only official feed connectors run through the local CLI. Live labels mean retrieved snapshots; ingestion is not scheduled. Fixture runs never establish live connector success.",
    }

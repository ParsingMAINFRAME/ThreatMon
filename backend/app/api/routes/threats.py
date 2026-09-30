from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.repository import get_threat_event, query_threat_cards
from app.db.session import get_db
from app.domain.threats.models import ThreatCategory
from app.domain.threats.schemas import ThreatDetailResponse, ThreatListResponse
from app.domain.threats.status import ThreatStatus


router = APIRouter(tags=["threats"])


@router.get("/threats", response_model=ThreatListResponse)
def list_threats(q: str | None = Query(default=None, max_length=200),
                 category: ThreatCategory | None = None, status: ThreatStatus | None = None,
                 data_mode: Literal["demo", "live"] | None = None,
                 min_priority: float = Query(default=0, ge=0, le=100),
                 sort: Literal["priority", "updated"] = "priority",
                 limit: int = Query(default=50, ge=1, le=100),
                 offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)) -> ThreatListResponse:
    cards, total, mode, snapshot_id = query_threat_cards(db, q=q, category=category, status=status,
                                                      data_mode=data_mode, min_priority=min_priority,
                                                      sort=sort, limit=limit, offset=offset)
    return ThreatListResponse(demo_data=mode == "demo", items=cards, data_mode=mode,
                              total=total, limit=limit, offset=offset, snapshot_id=snapshot_id)


@router.get("/threats/{threat_id}", response_model=ThreatDetailResponse)
def get_threat(threat_id: str, db: Session = Depends(get_db)) -> ThreatDetailResponse:
    threat = get_threat_event(db, threat_id)
    if threat is None:
        raise HTTPException(status_code=404, detail="Threat not found")
    return ThreatDetailResponse(demo_data=threat.is_demo, item=threat, data_mode="demo" if threat.is_demo else "live")

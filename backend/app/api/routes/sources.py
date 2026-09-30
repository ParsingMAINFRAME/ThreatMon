from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.repository import list_source_items
from app.db.session import get_db
from app.domain.sources.models import SourceItem


router = APIRouter(tags=["sources"])


@router.get("/sources", response_model=list[SourceItem])
def list_sources(db: Session = Depends(get_db)) -> list[SourceItem]:
    return list_source_items(db)

from pathlib import Path
from typing import Literal

from fastapi import APIRouter

from app.core.config import get_settings
from app.news.demo import demo_news
from app.news.models import NewsResponse
from app.news.service import read_news

router = APIRouter(tags=["news"])


@router.get("/news", response_model=NewsResponse)
def get_news(edition: Literal["demo", "snapshot"] = "demo") -> NewsResponse:
    return demo_news() if edition == "demo" else read_news(Path(get_settings().news_snapshot_path))

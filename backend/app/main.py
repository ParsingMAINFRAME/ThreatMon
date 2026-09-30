from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, ingest, sources, threats
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.init import init_db
from app.news.routes import router as news_router


configure_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.create_db_on_startup:
        init_db(seed_demo=settings.seed_demo_data)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description="Read-only, source-cited threat snapshots with official USGS/CISA ingestion and clearly labeled demo scenarios.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(threats.router)
app.include_router(sources.router)
app.include_router(ingest.router)
app.include_router(news_router)

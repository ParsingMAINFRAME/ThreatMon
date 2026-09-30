from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Threat Situation Room"
    app_env: str = "local"
    database_url: str = "sqlite:///./threat_situation_room.db"
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    create_db_on_startup: bool = True
    seed_demo_data: bool = True
    news_snapshot_path: str = "./.artifacts/news/nasa-snapshot.json"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

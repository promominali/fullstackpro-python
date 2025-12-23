from functools import lru_cache
from pydantic import AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Fullstack GCP App"
    environment: str = "dev"  # dev, staging, prod
    secret_key: str = "change-me"  # override in env/Cloud Run
    session_cookie_name: str = "session"

    database_url: str = "postgresql+psycopg2://postgres:postgres@db:5432/app"
    redis_url: str = "redis://redis:6379/0"

    gcp_project_id: str | None = None
    gcp_region: str | None = None
    pubsub_topic: str | None = None

    # Cloud Run specific
    cloud_run_service: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

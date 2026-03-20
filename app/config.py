from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Job Agent"
    database_url: str = "sqlite:///./jobs.db"
    request_timeout_seconds: int = 30
    user_agent: str = "job-agent/0.1"
    scheduler_enabled: bool = True
    daily_run_hour: int = 8
    daily_run_minute: int = 0
    timezone: str = "UTC"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


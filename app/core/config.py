"""Application configuration and settings providers."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings loaded from environment variables.

    Attributes:
        app_name: Display name of the service.
        app_env: Runtime environment name.
        app_host: Host interface for server binding.
        app_port: Port for server binding.
        app_log_level: Logging level for root logger.
        database_url: SQLAlchemy database URL.
        sqlalchemy_echo: Enables SQL query echo logging when True.
        document_storage_dir: Local directory for generated document files.
    """

    model_config = SettingsConfigDict(
        env_prefix="JOBKOI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="Jobkoi API")
    app_env: str = Field(default="local")
    app_host: str = Field(default="127.0.0.1")
    app_port: int = Field(default=8000)
    app_log_level: str = Field(default="INFO")
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/jobkoi"
    )
    sqlalchemy_echo: bool = Field(default=False)
    document_storage_dir: str = Field(default="storage/documents")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings.

    Returns:
        Loaded and validated settings object.
    """

    return Settings()

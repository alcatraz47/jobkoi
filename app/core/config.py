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
        import_storage_dir: Local directory for import source file storage.
        frontend_api_timeout_seconds: Frontend-to-backend HTTP timeout in seconds.
        profile_import_auto_approve_enabled: Enables confidence-based auto-approval.
        profile_import_auto_approve_min_confidence: Minimum confidence for auto-approval.
        profile_import_llm_enabled: Enables LLM-assisted import extraction stage.
        profile_import_llm_max_input_chars: Max characters sent to LLM during import extraction.
        ollama_base_url: Base URL for local/remote Ollama server.
        ollama_model: Ollama model name used by LLM helpers.
        ollama_timeout_seconds: Timeout for Ollama HTTP calls.
        ollama_max_retries: Retry count after initial Ollama call.
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
        default="postgresql+psycopg://jobkoi:jobkoi@localhost:5432/jobkoi"
    )
    sqlalchemy_echo: bool = Field(default=False)
    document_storage_dir: str = Field(default="storage/documents")
    import_storage_dir: str = Field(default="storage/imports")
    frontend_api_timeout_seconds: float = Field(default=180.0, gt=0)
    profile_import_auto_approve_enabled: bool = Field(default=True)
    profile_import_auto_approve_min_confidence: int = Field(default=94, ge=0, le=100)
    profile_import_llm_enabled: bool = Field(default=False)
    profile_import_llm_max_input_chars: int = Field(default=24000, ge=1000)
    ollama_base_url: str = Field(default="http://127.0.0.1:11434")
    ollama_model: str = Field(default="qwen2.5:3b")
    ollama_timeout_seconds: float = Field(default=120.0, gt=0)
    ollama_max_retries: int = Field(default=1, ge=0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings.

    Returns:
        Loaded and validated settings object.
    """

    return Settings()

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    app_name: str = "AI Playground"
    app_version: str = "0.1.0"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    docs_enabled: bool = True
    cors_origins: list[str] = []

    database_url: str = "postgresql+asyncpg://ai_playground:ai_playground@db:5432/ai_playground"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5-mini"
    memory_refresh_model: str = "gpt-5-mini"
    openai_timeout_seconds: float = Field(default=30.0, gt=0)
    openai_max_retries: int = Field(default=2, ge=0, le=10)
    chat_max_prompt_length: int = Field(default=10_000, ge=1, le=100_000)
    codex_cli_path: str = "/usr/local/bin/codex"
    codex_home: str = "/home/app/.codex"

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.upper()


@lru_cache
def get_settings() -> Settings:
    return Settings()

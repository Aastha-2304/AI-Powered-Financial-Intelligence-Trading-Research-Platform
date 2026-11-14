"""
Application Settings & Environment Configuration.
Typed via Pydantic Settings, loaded from .env.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Runtime application configuration."""
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_ENV: str = Field(default="development", description="Application environment")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # Project directories
    BASE_DIR: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent)
    DATABASE_PATH: str = Field(default="database/financial_warehouse.duckdb")
    UPLOAD_DIR: str = Field(default="data/raw")
    REPORTS_DIR: str = Field(default="data/reports")
    FIXTURES_DIR: str = Field(default="data/fixtures")

    # LLM Settings
    GROQ_API_KEY: str = Field(default="", description="Groq API Key for LLaMA 3.3")
    GROQ_MODEL: str = Field(default="llama-3.3-70b-versatile", description="Configurable Groq Model ID")

    # Single-user context stub
    DEFAULT_USER_ID: str = Field(default="usr_local_analyst")

    @property
    def resolved_db_path(self) -> Path:
        p = Path(self.DATABASE_PATH)
        if p.is_absolute():
            return p
        return self.BASE_DIR / p

    @property
    def resolved_upload_dir(self) -> Path:
        p = Path(self.UPLOAD_DIR)
        return p if p.is_absolute() else self.BASE_DIR / p

    @property
    def resolved_reports_dir(self) -> Path:
        p = Path(self.REPORTS_DIR)
        return p if p.is_absolute() else self.BASE_DIR / p

    @property
    def resolved_fixtures_dir(self) -> Path:
        p = Path(self.FIXTURES_DIR)
        return p if p.is_absolute() else self.BASE_DIR / p


settings = Settings()


def get_settings() -> Settings:
    """Returns the application settings singleton."""
    return settings

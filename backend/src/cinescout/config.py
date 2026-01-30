"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/cinescout"

    # Redis (optional for MVP)
    redis_url: str = "redis://localhost:6379"

    # TMDb API
    tmdb_api_key: str = ""

    # Scraping settings
    scrape_timeout: int = 30
    scrape_max_retries: int = 3

    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000


# Global settings instance
settings = Settings()

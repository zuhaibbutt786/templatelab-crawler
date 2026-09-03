"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql://templatelab:templatelab@localhost:5432/templatelab"

    # Crawler
    crawl_delay: float = 2.0
    max_concurrent_requests: int = 2
    request_timeout: int = 30
    max_retries: int = 3
    crawl_interval_hours: int = 168  # 7 days
    force_recrawl: bool = False

    user_agent: str = (
        "TemplateLabEthicalCrawler/1.0 (+https://example.com/bot; research)"
    )

    use_playwright: bool = False
    headless: bool = True

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Base site
    base_url: str = "https://templatelab.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()

import os
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_async_database_url(url: str) -> str:
    """
    Ensure DATABASE_URL uses an async SQLAlchemy driver.

    Bare postgresql:// defaults to psycopg2 (sync), which breaks create_async_engine.
    """
    if not url:
        return url
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    prefix, _, rest = url.partition("://")
    if prefix == "postgresql" and "+" not in prefix:
        return f"postgresql+asyncpg://{rest}"
    if prefix == "postgresql+psycopg2":
        return f"postgresql+asyncpg://{rest}"
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "sqlite+aiosqlite:///./tazakhabar.db"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        return normalize_async_database_url(v)

    OPENROUTER_API_KEY: str = "your_key_here"
    GROQ_API_KEY: str = "your_key_here"
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_STORAGE_BUCKET: str = "resumes"
    SUPABASE_EMAIL_FROM: str = ""
    EMAIL_SMTP_HOST: str = ""
    EMAIL_SMTP_PORT: int = 465
    EMAIL_SMTP_USER: str = ""
    EMAIL_SMTP_PASSWORD: str = ""
    EMAIL_SMTP_USE_TLS: bool = True
    ALLOWED_ORIGINS: str = (
        "http://localhost:3000,https://tazakhabar.vercel.app,https://*.vercel.app"
    )
    LOG_LEVEL: str = "INFO"
    LOG_DIR: Path = Path("logs")

    # Embeddings / RAG (sentence-transformers + torch). Disable on low-memory hosts.
    EMBEDDINGS_ENABLED: bool = True

    # Render / keep-alive (Render free tier idles after inactivity)
    # If KEEPALIVE_ENABLED is true, the app will periodically send an HTTP GET
    # to KEEPALIVE_URL (or derived from RENDER_EXTERNAL_URL) to keep the service warm.
    RENDER_EXTERNAL_URL: str = ""
    KEEPALIVE_ENABLED: bool = False
    KEEPALIVE_INTERVAL_SEC: int = 14 * 60
    KEEPALIVE_URL: str = ""

    # Notebook CSV pipeline (job_scraper.ipynb → jobs_output.csv)
    NOTEBOOK_SYNC_ENABLED: bool = True
    NOTEBOOK_SYNC_INTERVAL_SEC: int = 15
    TAZA_API_URL: str = "http://localhost:8000"

    @property
    def origins_list(self) -> list[str]:
        """Parse ALLOWED_ORIGINS into a list of origins."""
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]


settings = Settings()

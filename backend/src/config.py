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
        env_file=(
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"
            ),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "sqlite+aiosqlite:///./tazakhabar.db"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        return normalize_async_database_url(v)

    # Pyronites (PyroCore): auth, tables and file storage.
    PYRONITES_URL: str = ""
    PYRONITES_KEY: str = ""
    PYRONITES_PROJECT_ID: str = ""
    PYRONITES_TIMEOUT_SEC: float = 30.0

    # Browser session: httpOnly cookie that carries the signed session.
    AUTH_SESSION_COOKIE: str = "tk_session"
    AUTH_SESSION_SECRET: str = ""
    AUTH_SESSION_TTL_SEC: int = 60 * 60 * 24 * 14
    # When true, private endpoints reject anonymous callers.
    AUTH_REQUIRED: bool = True
    # Cross-site cookie settings: the frontend (Vercel) and API (Render) are
    # different sites, so production needs SameSite=None + Secure. Local
    # development on http://localhost needs Lax without Secure.
    AUTH_COOKIE_SECURE: bool = True
    AUTH_COOKIE_SAMESITE: str = "none"

    # Public URLs. API_PUBLIC_URL is where the OAuth provider sends the
    # browser back to, FRONTEND_URL is where we send the user after sign in.
    API_PUBLIC_URL: str = ""
    FRONTEND_URL: str = ""

    # OAuth clients for Google and GitHub (the API is the OAuth client).
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""

    # Guards the write endpoints (scrape trigger, CSV load, embeddings backfill).
    ADMIN_TOKEN: str = ""

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
        "http://localhost:3000,https://tazakhabar.vercel.app,https://tazakhabar3021.vercel.app"
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

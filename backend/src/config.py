import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "sqlite+aiosqlite:///./tazakhabar.db"
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

    @property
    def origins_list(self) -> list[str]:
        """Parse ALLOWED_ORIGINS into a list of origins."""
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]


settings = Settings()

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    DATABASE_URL: str = "sqlite+aiosqlite:///./tazakhabar-backend/tazakhabar.db"
    GEMINI_API_KEY: str = "your_key_here"
    ALLOWED_ORIGINS: str = "http://localhost:3000,https://tazakhabar.vercel.app,https://*.vercel.app"
    LOG_LEVEL: str = "INFO"
    LOG_DIR: Path = Path("logs")

    @property
    def origins_list(self) -> list[str]:
        """Parse ALLOWED_ORIGINS into a list of origins."""
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]


settings = Settings()

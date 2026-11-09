from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from environment variables or a `.env` file"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Strength Journal"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/strength_journal"

    # Sessions (see app/auth/sessions.py)
    session_cookie_name: str = "session"
    # Send the session cookie over HTTPS only; set to false for plain-HTTP local development
    cookie_secure: bool = True
    # Unsafe requests (POST/PUT/PATCH/DELETE) carrying any other Origin header are rejected
    allowed_origin: str = "http://localhost:5173"
    session_days: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()

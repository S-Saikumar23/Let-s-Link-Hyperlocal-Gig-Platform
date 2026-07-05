from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Let's Link"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Database — loaded from .env
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/letslink"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@localhost:5432/letslink"

    # JWT Authentication — loaded from .env
    SECRET_KEY: str = "change-me-in-env-file"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Razorpay — loaded from .env
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # CORS — loaded from .env (comma-separated string → list)
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ]

    # File uploads
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 5 * 1024 * 1024  # 5MB

    # Matching
    DEFAULT_RADIUS_KM: int = 5

    # Sentry (Error Tracking)
    SENTRY_DSN: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

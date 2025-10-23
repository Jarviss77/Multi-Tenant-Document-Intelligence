import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Multi-Tenant-Document-Intelligence"
    SECRET_KEY: str = os.getenv("SECRET_KEY","your_secret_key")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT:int = int(os.getenv("REDIS_PORT", 6379))
    UPLOADS_PER_MINUTE: int = 2
    SEARCHES_PER_MINUTE: int = 100

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@db:5432/document_intelligence"
    )

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY")

    class Config:
        env_file = ".env"

settings = Settings()
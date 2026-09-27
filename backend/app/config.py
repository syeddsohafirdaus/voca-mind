import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings and environment configuration."""

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/voca_mind"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Firebase Authentication Configuration
    FIREBASE_PROJECT_ID: str | None = None
    FIREBASE_CREDENTIALS_PATH: str | None = None
    FIREBASE_AUTH_EMULATOR_HOST: str | None = None

    # Qdrant Vector Store & Embedding Configuration
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_NAME: str = "voca_mind_knowledge"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

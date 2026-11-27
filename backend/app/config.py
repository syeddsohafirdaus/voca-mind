
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings and environment configuration."""

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/voca_mind"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Firebase Authentication
    FIREBASE_PROJECT_ID: str | None = None
    FIREBASE_CREDENTIALS_PATH: str | None = None
    FIREBASE_AUTH_EMULATOR_HOST: str | None = None

    # Qdrant and embeddings
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_NAME: str = "voca_mind_knowledge"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536
    EMBEDDING_PROVIDER: str = "auto"

    # Local embedding configuration
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_EMBEDDING_TIMEOUT_SECONDS: float = 120.0

    # Qdrant storage configuration
    QDRANT_MODE: str = "remote"
    QDRANT_LOCAL_PATH: str = ""

    KNOWLEDGE_APPROVAL_PUBLIC_KEY: str = ""

    # OpenAI
    OPENAI_API_KEY: str | None = None
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"
    OPENAI_TIMEOUT_SECONDS: float = 30.0

    # Local Ollama
    AI_PROVIDER: str = "auto"
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"
    OLLAMA_TIMEOUT_SECONDS: float = 180.0

    # Development fallback
    ALLOW_DEV_FAKE_GENERATOR: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


"""Application configuration (Phase 1)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = travelling-agent/ (folder holding .env), resolved from this
# file so the backend loads .env no matter which CWD uvicorn starts from.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_PROJECT_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "travel-agent"
    ENVIRONMENT: str = "local"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "postgresql+asyncpg://travel:travel@localhost:5432/travel_db"
    SYNC_DATABASE_URL: str = "postgresql+psycopg2://travel:travel@localhost:5432/travel_db"

    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_BASE_URL: str = ""
    # Groq (OpenAI-compatible). Set GROQ_API_KEY to use Groq instead of OpenAI.
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    # "auto" (default): Groq if GROQ_API_KEY set, else OpenAI if OPENAI_API_KEY set.
    # Force with "groq" or "openai".
    LLM_PROVIDER: str = "auto"
    LLM_TIMEOUT_SECONDS: int = 60

    # --- RAG / Phase 2 (local sentence-transformers, no OpenAI key needed) ---
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150
    RAG_TOP_K: int = 5
    RAG_DATA_DIR: str = "data/documents"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

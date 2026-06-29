from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "NL Query API"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str = "change-this-to-a-long-random-secret-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Database
    DATABASE_URL: str = "sqlite:///./app.db"

    # Hugging Face
    HF_TOKEN: str = ""
    HF_MODEL: str = "meta-llama/Llama-3.3-70B-Instruct"

    # ChromaDB (optional RAG)
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    USE_RAG: bool = False

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
